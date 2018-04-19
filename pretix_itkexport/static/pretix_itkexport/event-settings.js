(function ($) {
    $(function() {
        // Make a non-empty "PSP" metadata value readonly.
        $('.metadata-group label[for]').each(function () {
            var text = $.trim($(this).text());
            if ('PSP' === text) {
                var field = $('#'+$(this).attr('for'))
                var value = $.trim($(field).val());
                if (value) {
                    $(field).prop('readonly', true);
                }
            }
        });
    });
}(jQuery));
