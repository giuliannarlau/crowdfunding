
async function processDonation() {
    try {

        checkAmount();

        // Build transaction envelope
        let transactionXdr = await buildDonationTransaction();

        // Sign transaction with Freighter
        let signedTransactionXdr = await signingTransaction(transactionXdr);

        // Send transaction to Stellar and display hash
        let hash = await sendTransaction(signedTransactionXdr);
        document.getElementById("modalTitle").innerHTML = "Donation completed!";
        document.getElementById("modalBody").textContent = "Here is your hash:\n" + hash + "\nThis transaction will be available on your account page.";

        const modal = new bootstrap.Modal(document.getElementById("alertModal"));
        modal.show();

    } catch (error) {
        return console.log("Error: ", error);
    }
};


// Send request to build transaction envelope
async function buildDonationTransaction() {

    // Avoid form submission
    event.preventDefault();

    // Get project info
    const project_id = document.getElementById("projectId").value;
    const amount = document.getElementById("donationAmount").value;
    const body = {
        project_id: project_id,
        amount: amount
    };

    const requestOptions = {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(body)
    };

    try {
        let response = await fetch("/donate", requestOptions);
        let data = await response.json();
        if (data.err == 400) {
            let error = "Invalid amount, please check if it's a valid integer.";
            alert(error);
            throw new Error(error);
        }

        return data.transaction_xdr;
    } catch (error) {
        console.error(error);
        throw error;
    }
};
