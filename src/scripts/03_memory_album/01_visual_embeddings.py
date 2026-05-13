import os
import sys

_d = os.path.abspath(__file__)
while not os.path.exists(os.path.join(_d, "config.py")):
    _p = os.path.dirname(_d)
    if _p == _d:
        raise RuntimeError("config.py introuvable")
    _d = _p
sys.path.insert(0, _d)

from config import (  # noqa: E402
    build_spark_session,
    WAREHOUSE,
    ALBUM_PHOTOS_DIR,
    MODELS_CACHE_DIR,
)
from pyspark.sql.types import (  # noqa: E402
    StructType,
    StructField,
    StringType,
    FloatType,
    DoubleType,
    ArrayType,
    LongType,
)
from delta.tables import DeltaTable  # noqa: E402
import glob  # noqa: E402
import yaml  # noqa: E402


def _load_config() -> dict:
    config_path = os.path.join(_d, "config.yaml")
    if os.path.exists(config_path):
        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        return cfg.get("memory_album", {})
    return {}


def extract_exif(photo_path: str) -> dict:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
    result = {"gps_lat": None, "gps_lon": None, "photo_date": None}
    try:
        img = Image.open(photo_path)
        exif_data = img._getexif()
        if exif_data is None:
            return result
        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == "GPSInfo":
                gps = {}
                for key, val in value.items():
                    gps[GPSTAGS.get(key, key)] = val
                if "GPSLatitude" in gps and "GPSLongitude" in gps:
                    def dms_to_dd(dms, ref):
                        d, m, s = [float(x) for x in dms]
                        dd = d + m / 60 + s / 3600
                        return -dd if ref in ("S", "W") else dd
                    result["gps_lat"] = dms_to_dd(gps["GPSLatitude"], gps.get("GPSLatitudeRef", "N"))
                    result["gps_lon"] = dms_to_dd(gps["GPSLongitude"], gps.get("GPSLongitudeRef", "E"))
            elif tag == "DateTimeOriginal":
                from datetime import datetime
                try:
                    dt = datetime.strptime(str(value), "%Y:%m:%d %H:%M:%S")
                    result["photo_date"] = dt.isoformat()
                except Exception:
                    pass
    except Exception:
        pass
    return result


def _load_model(model_name: str, models_cache: str):
    """Load the vision model based on its name. Returns (model, processor_or_preprocess, device, kind).

    kind = "blip2" | "openclip"
    BLIP-2 model names start with "Salesforce/blip2".
    Everything else is treated as an OpenCLIP / HuggingFace CLIP model.
    """
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"

    if model_name.startswith("Salesforce/blip2"):
        from transformers import Blip2Processor, Blip2Model
        print(f"  Loading BLIP-2 ({model_name}) on {device}...", flush=True)
        processor = Blip2Processor.from_pretrained(model_name, cache_dir=models_cache)
        model = Blip2Model.from_pretrained(model_name, cache_dir=models_cache).to(device)
        model.eval()
        return model, processor, device, "blip2"
    else:
        import open_clip
        print(f"  Loading OpenCLIP ({model_name}) on {device}...", flush=True)
        hf_name = f"hf-hub:{model_name}" if "/" in model_name else model_name
        model, _, preprocess = open_clip.create_model_and_transforms(
            hf_name, cache_dir=models_cache
        )
        model = model.to(device)
        model.eval()
        return model, preprocess, device, "openclip"


def run_inference(photo_files: list, model_name: str, batch_size: int, models_cache: str) -> list:
    """Pure Python inference loop — faithful to the notebook approach."""
    import torch
    from PIL import Image

    model, processor_or_preprocess, device, kind = _load_model(model_name, models_cache)
    print(f"  Model ready. Running inference on {len(photo_files)} photos...", flush=True)

    rows = []
    total = len(photo_files)
    for i in range(0, total, batch_size):
        batch = photo_files[i:i + batch_size]
        for j, path in enumerate(batch):
            idx = i + j + 1
            print(f"  [{idx}/{total}] {os.path.basename(path)}", flush=True)
            photo_id = os.path.splitext(os.path.basename(path))[0]
            exif = extract_exif(path)
            base = {
                "photo_id": photo_id,
                "path": path,
                "filename": os.path.basename(path),
                "caption": "",
                "lat": exif["gps_lat"],
                "lon": exif["gps_lon"],
                "exif_date": exif["photo_date"],
                "has_gps": exif["gps_lat"] is not None,
            }
            try:
                img = Image.open(path).convert("RGB")
                if kind == "blip2":
                    inputs = processor_or_preprocess(images=img, return_tensors="pt").to(device)
                    with torch.no_grad():
                        emb = model.vision_model(**inputs).last_hidden_state[:, 0, :].cpu().numpy()[0]
                else:
                    img_tensor = processor_or_preprocess(img).unsqueeze(0).to(device)
                    with torch.no_grad():
                        emb = model.encode_image(img_tensor).cpu().numpy()[0]
                rows.append({**base, "embedding": emb.tolist()})
            except Exception as e:
                print(f"  ⚠ erreur: {e}", flush=True)
                rows.append({**base, "embedding": []})

    return rows


def main():
    spark = build_spark_session(
        "MyDigitalTwin-MemoryAlbum-Embeddings",
        driver_memory="4g",
        shuffle_partitions=8,
        delta=True,
        snappy=True,
    )
    spark.sparkContext.setLogLevel("WARN")
    try:
        ma_config = _load_config()
        model_name = ma_config.get("model", "Salesforce/blip2-opt-2.7b")
        batch_size = ma_config.get("batch_size", 8)

        photo_files = []
        for ext in ("*.jpg", "*.JPG", "*.jpeg", "*.JPEG", "*.png", "*.PNG"):
            photo_files += glob.glob(os.path.join(ALBUM_PHOTOS_DIR, "**", ext), recursive=True)

        if not photo_files:
            print(f"  ⚠ No photos found in {ALBUM_PHOTOS_DIR}")
            return

        print(f"  {len(photo_files)} photos found — running inference...")
        rows = run_inference(photo_files, model_name, batch_size, MODELS_CACHE_DIR)

        if not rows:
            print("  ⚠ No embeddings generated")
            return

        schema = StructType([
            StructField("photo_id", StringType()),
            StructField("path", StringType()),
            StructField("filename", StringType()),
            StructField("caption", StringType()),
            StructField("lat", DoubleType()),
            StructField("lon", DoubleType()),
            StructField("exif_date", StringType()),
            StructField("has_gps", StringType()),
            StructField("embedding", ArrayType(FloatType())),
        ])

        df = spark.createDataFrame(rows, schema=schema)

        table_path = os.path.join(WAREHOUSE, "memory_album", "photo_embeddings")
        if DeltaTable.isDeltaTable(spark, table_path):
            DeltaTable.forPath(spark, table_path).alias("t").merge(
                df.alias("s"), "t.photo_id = s.photo_id"
            ).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()
        else:
            df.write.format("delta").mode("overwrite").save(table_path)

        count = spark.read.format("delta").load(table_path).count()
        print(f"  ✓ memory_album/photo_embeddings — {count:,} lignes")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
