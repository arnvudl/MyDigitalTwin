(function () {
  var currentIndex = 0;
  var photoUrls = [];

  function openLightbox(urls, index) {
    photoUrls = urls;
    currentIndex = index;
    updateImage();
    var overlay = document.getElementById('lightbox-overlay');
    if (overlay) {
      overlay.style.display = 'flex';
      document.body.style.overflow = 'hidden';
    }
  }

  function closeLightbox() {
    var overlay = document.getElementById('lightbox-overlay');
    if (overlay) overlay.style.display = 'none';
    document.body.style.overflow = '';
  }

  function navigate(dir) {
    if (!photoUrls.length) return;
    currentIndex = (currentIndex + dir + photoUrls.length) % photoUrls.length;
    updateImage();
  }

  function updateImage() {
    var img = document.getElementById('lightbox-img');
    var counter = document.getElementById('lightbox-counter');
    if (img) img.src = photoUrls[currentIndex];
    if (counter) counter.textContent = (currentIndex + 1) + ' / ' + photoUrls.length;
  }

  // Event delegation — works after React re-renders
  document.addEventListener('click', function (e) {
    var target = e.target;

    // Close on overlay background click
    if (target && target.id === 'lightbox-overlay') {
      closeLightbox();
      return;
    }
    if (target && target.id === 'lightbox-close') { closeLightbox(); return; }
    if (target && target.id === 'lightbox-prev')  { navigate(-1); return; }
    if (target && target.id === 'lightbox-next')  { navigate(1); return; }

    // Open on photo click
    var img = target.closest ? target.closest('.photo-item') : null;
    if (!img) return;
    var grid = document.getElementById('photo-grid-container');
    var allImgs = grid ? Array.from(grid.querySelectorAll('.photo-item')) : [];
    var urls = allImgs.map(function (i) { return i.src; });
    var index = allImgs.indexOf(img);
    if (index < 0) index = 0;
    openLightbox(urls, index);
  });

  document.addEventListener('keydown', function (e) {
    var overlay = document.getElementById('lightbox-overlay');
    if (!overlay || overlay.style.display === 'none') return;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') navigate(1);
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') navigate(-1);
    else if (e.key === 'Escape') closeLightbox();
  });
})();
