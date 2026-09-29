let currentStep = 1;
let uploadedFileUploaded = false;

function setStep(step) {
    document.querySelectorAll('.step-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.step-item').forEach(el => el.classList.remove('active'));
    
    document.getElementById(`step-${step}`).classList.add('active');
    document.getElementById(`indicator-${step}`).classList.add('active');
    currentStep = step;
}

function validateAndNext(nextStep) {
    if (!uploadedFileUploaded) {
        showModal("Upload Required", "Please select and upload at least one valid document before proceeding.");
        return;
    }
    setStep(nextStep);
}

function showModal(title, message) {
    document.getElementById('modalTitle').innerText = title;
    document.getElementById('modalMessage').innerText = message;
    document.getElementById('customModal').style.display = 'flex';
}

function closeModal() {
    document.getElementById('customModal').style.display = 'none';
}

function handleFileUpload() {
    const fileInput = document.getElementById('fileInput');
    if (fileInput.files.length > 0) {
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);

        fetch('/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if(data.success) {
                uploadedFileUploaded = true;
                document.getElementById('lblTotalPages').innerText = data.total_pages;
                showModal("Success", "Document uploaded and processed successfully!");
            } else {
                showModal("Error", data.error || "Failed to upload file.");
            }
        })
        .catch(err => {
            showModal("Error", "An error occurred during file upload.");
        });
    }
}

function proceedToPayment() {
    showModal("Notice", "Kiosk Printer is currently online and ready for processing payment.");
}
