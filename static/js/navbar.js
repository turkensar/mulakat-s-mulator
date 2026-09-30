/* Profil menüsü (<details id="profile-menu">): menü dışına tıklayınca ya da Esc'ye basınca kapanır.
   JavaScript yoksa <details> yine de açılıp kapanır. */
(function () {
    var menu = document.getElementById('profile-menu');
    if (!menu) { return; }

    document.addEventListener('click', function (event) {
        if (menu.open && !menu.contains(event.target)) {
            menu.open = false;
        }
    });

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && menu.open) {
            menu.open = false;
            var button = menu.querySelector('summary');
            if (button) { button.focus(); }
        }
    });
})();
