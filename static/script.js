
// Timing
window.onload = function() {
    var now = new Date().getTime();
    var page_load_time = now - performance.timing.navigationStart;
    console.log("User-perceived page loading time: " + page_load_time);
  }


/* NEW PROJECT AND PROJECT PAGE (MODAL) */

// Get current date to set as min for date inputs
function getCurrentDate(minDateInput) {
    let today = new Date();
    minExpireDate = today.toISOString().split('T')[0];
    minDateInput.min = minExpireDate;
}


// Check if user connected wallet
function checkUser(element) {
    console.log(element);
    if (!element.name) {
        document.getElementById("modalBody").innerHTML = "You need to connect you wallet first!";
        const modal = new bootstrap.Modal(document.getElementById("alertModal"));
        modal.show();
        return false;
    } else {
        if (element.id == "startProjectLink") {
            window.location.href = "/newproject";
        }
    }
    return true;
};


// Get user public key from Freighter
async function fetchKey() {

    // Prevent default form button behaviour
    event.preventDefault();

    // Checks if Freighter is connected
    if (await window.freighterApi.isConnected()) {
        if (typeof window.freighterApi !== "undefined") {
            try {
                const publicKey = await window.freighterApi.getPublicKey();
                await sendKey(publicKey);
            } catch (error) {
                console.log(await window.freighterApi.getPublicKey());
                alert("You have to share your key to log in");
                throw error;
            }
        } else {
            console.log("Object not defined");
            alert("Freighter ran through some problem, please try again later.");
        }
    }
    else {
        alert("You need to install Freighter extension first. Click on 'Create Wallet'");
    }
};


// Send user public key to the server
async function sendKey(publicKey) {

    const requestOptions = {
        method: "POST",
        headers: {
            "Content-Type": "multipart/form-data",
        },
        body: publicKey,
    };

    try {
        const response = await fetch("/", requestOptions);
        if (response.ok) {
            location.reload();
        } else {
            console.log("Error: Public key was NOT send.");
        }
    } catch (error) {
        console.log("Request error", error);
        alert("Error while sending your public key, please try again later.");
    }
};

/*  PROJECT PAGE */

// Check valid donation amount
function checkAmount() {

    const donationAmount = Number(document.getElementById("donationAmount").value);
    if (donationAmount <= 0) {
        alert("The minimun donation amount is 1 lumen.");
        throw new Error(400);
    }
    return true;
};


// Sign transaction with Freighter (for users and admin)
async function signingTransaction(transactionXdr) {

    try {
        // Get public key
        const public_key = window.freighterApi.getPublicKey();
        const publicKeyString = public_key.toString();

        // Call Freighter to sign transaction
        const signedTransaction = await window.freighterApi.signTransaction(transactionXdr, "TESTNET", publicKeyString);
        return signedTransaction;

    // Show error if signing fails
    } catch (error) {
        console.error("Error signing transaction:", error);
        throw error;
    }
};

// Send a request with transaction signed (users and admin)
async function sendTransaction(signedTransactionXdr) {

    const requestOptions = {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(signedTransactionXdr)
    };

    try {
        let response = await fetch("/send_transaction", requestOptions);
        let data = await response.json();
        return data.hash;

    // Show error if submit fails
    } catch (error) {
        throw error;
    }

};
