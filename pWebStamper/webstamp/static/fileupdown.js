/*global saveAs, self*/

"use strict";
$(document).ready(function(event){
    var upload_filename = $("#upload-filename");
    var upload_spinner = $("#upload-spinner");
    var dice_report = $("#dice_report");
    var download_machine = $("#download-machine");
    var download_filename = $("#download-filename");
    var download_btn = $("#download-btn");

    if (!dice_report[0].readOnly) {
        // Before stamping, hide download-stamp machinery.
        //
        download_machine.addClass('hidden');

        // Upload-button populates dice-report Text-Area.
        //
        upload_filename.change(function(event) {
            //var fpath = upload_filename[0].files[0].name;
            var file =  event.target.files[0];
            if (file) {
                upload_spinner.removeClass("hidden");
                var reader = new FileReader();
                reader.onload = function(event) {
                    dice_report.val(event.target.result);
                    upload_spinner.addClass("hidden");
                };

                reader.readAsText(file);
            }
        });

        // If user manually edits dice-report,
        // reloading the *same* file does nothing above (no "change"),
        // so reset file-input on manual edits
        //
        dice_report.change(function(event) {
            upload_filename.val('');
        });
    } else {
        download_machine.removeClass('hidden');

        // Download-button saves locally the contents of dice-report Text-Area.
        //
        download_btn.click(function(event){
            saveAs(
                new self.Blob(
                    [dice_report.val()],
                    {type: "text/plain;charset=" + document.characterSet}
                ),
                (download_filename.val() || download_filename[0].placeholder || "stamp.txt"),
                true // no_auto_bom
            );
        });
    }
});
