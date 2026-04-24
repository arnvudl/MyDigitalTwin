window.dash_clientside = window.dash_clientside || {};
window.dash_clientside.reco = {
    animateScoreCounter: function(n, store) {
        if (!store || store.target === 0) return [window.dash_clientside.no_update, store, true];
        var current = store.current || 0;
        var target  = store.target  || 0;
        if (current >= target) return [target + "%", store, true];
        var step = Math.max(1, Math.ceil((target - current) / 12));
        var next = Math.min(current + step, target);
        return [next + "%", {target: target, current: next}, next >= target];
    }
};
