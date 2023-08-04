
let imagePreview = document.getElementById('imagePreview');
let cropper;

function showImagePreview(imgInp) {
    let imagePreview = document.getElementById('imagePreview');

    const file = imgInp.files[0];
    if (file.size > 400000) {

        // TO DO: make it a modal
        alert("You can only upload images up to 400KB.");

    } else {

        imagePreview.src = URL.createObjectURL(file);
        imagePreview.onload = () => {
            URL.revokeObjectURL(imagePreview.src);
        }

        cropper = new Cropper(imagePreview, {
            aspectRatio: 1,
            viewMode: 3,
        })

        document.getElementById("cropImageBtn").hidden = false;
        document.getElementById("cropImageBtn").disabled = false;
    }
}


function cropImage() {

    let croppedImage = cropper.getCroppedCanvas().toDataURL("image/jpg", 0.2);
    let outputImage = document.getElementById("imageCropped");
    outputImage.src = croppedImage;
    outputImage.hidden = false;
    document.getElementById("croppedImgCol").hidden = false;

    document.getElementById("base64Image").value = croppedImage;

}