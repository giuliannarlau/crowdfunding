
let imagePreview = document.getElementById('imagePreview');
let cropper;
let outputImage = document.getElementById("imageCropped");
let base64Img= document.getElementById("base64Image");

function showImagePreview(imgInp) {

    const file = imgInp.files[0];

    if (file.size > 400000) {

        document.getElementById("modalTitle").innerHTML = "Oops! The image size is too large";
        document.getElementById("modalBody").textContent = "Please choose an image that is 400KB or smaller.";

        const modal = new bootstrap.Modal(document.getElementById("alertModal"));
        modal.show();

    } else {

        if (cropper) {
            cropper.destroy();
        }

        imagePreview.src = URL.createObjectURL(file);
        imagePreview.onload = () => {
            URL.revokeObjectURL(imagePreview.src);
        }

        cropper = new Cropper(imagePreview, {
            aspectRatio: 1,
            viewMode: 3,
        });
        
        const reader = new FileReader();
        reader.onloadend = function() {
            base64Img.value = reader.result;
        }

        reader.readAsDataURL(file);
        outputImage.src = URL.createObjectURL(file);

        outputImage.hidden = false;
        document.getElementById("croppedImgCol").hidden = false;
        document.getElementById("cropImageBtn").hidden = false;
        document.getElementById("cropImageBtn").disabled = false;

    }
}


function cropImage() {

    let croppedImage = cropper.getCroppedCanvas().toDataURL("image/jpg", 0.2);
    outputImage.src = croppedImage;
    base64Img.value = croppedImage;

}