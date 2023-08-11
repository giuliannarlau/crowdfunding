
// Timing
window.onload = function() {
    var now = new Date().getTime();
    var page_load_time = now - performance.timing.navigationStart;
    console.log("User-perceived page loading time: " + page_load_time);
  }

  function sortList(option) {
    console.log(option);
}


/* NEW PROJECT AND PROJECT PAGE (MODAL) */

// Get current date to set as min for date inputs
function getCurrentDate(minDateInput) {
    let today = new Date();
    minExpireDate = today.toISOString().split('T')[0];
    minDateInput.min = minExpireDate;
}


/* INDEX */

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

/* LAYOUT */

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

async function processDonation() {
    try {

        checkAmount();

        // Build transaction envelope
        let transactionXdr = await buildTransaction();

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
async function buildTransaction() {
    // TO DO: build this on backend

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

/* CONTROL PANEL (ADMIN) */

// Check and uncheck all checkboxes
function selectAll(source) {
    // TO DO: handle when user checks/unchecks all after selecting one ore more projects

    let checkboxes;
    if (source.value == "selectAllFunds") {
        console.log("Inside if funds");
        checkboxes = document.getElementsByName("fund_checkbox");
    }
    else if (source.value == "selectAllRefunds") {
        checkboxes = document.getElementsByName("refund_checkbox");
    }
    else {
        console.log("Invalid button");
    }

    for (let i=0; i < checkboxes.length; i++) {
        if (checkboxes[i].type == "checkbox") {
            if (checkboxes[i].checked == true) {
                checkboxes[i].checked = false;
            } else {
                checkboxes[i].checked = true;
            }
        }
    }
}


// Send a request with selected projects info for server to validate and builds modal to confirm transactions
async function processAdminAction(operationType) {

    const projectRows = document.querySelectorAll(".projectRow2");
    const selectedProjectIds = [];

    projectRows.forEach((row) => {
        const checkbox = row.querySelector(".admin-project-checkbox");
        if (checkbox.checked) {
            const projectId = checkbox.value;
            selectedProjectIds.push(projectId);
        }
    });
    console.log(selectedProjectIds);

    if (selectedProjectIds.length === 0) {
        alert("Please select at least one project.");
        return;
    }

    try {
        const responseFund = await fetch("/controlpanel", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Operation-Type": operationType,
            },
            body: JSON.stringify({ selected_project_ids: selectedProjectIds }),
        });

        let data = await responseFund.json();
        let responseProjects = data.admin_action_projects;
        const projectsForm = document.getElementById("projectsForm");
        projectsForm.innerHTML = "";

        // Table
        const table = document.createElement("table");
        table.classList.add("table");
        table.setAttribute("project_id", "modalAdminTable");

        // Headers
        const headerRow = document.createElement("tr");
        const headers = ["ID", "Name", "Destination Account", "Donations"];
        headers.forEach((headerText) => {
            const headerCell = document.createElement("th");
            headerCell.textContent = headerText;
            headerRow.appendChild(headerCell);
        });

        // Add header to table
        table.appendChild(headerRow);

        // Add one row per project
        responseProjects.forEach((project) => {
            const dataRow = document.createElement("tr");
            dataRow.classList.add("fundProjectRow");

            // Add one cell for each project info
            const idCell = document.createElement("td");
            idCell.textContent = project.project_id;
            dataRow.appendChild(idCell);

            const nameCell = document.createElement("td");
            nameCell.textContent = project.name;
            dataRow.appendChild(nameCell);

            const publicKeyCell = document.createElement("td");
            publicKeyCell.textContent = project.public_key;
            dataRow.appendChild(publicKeyCell);

            const donationsCell = document.createElement("td");
            donationsCell.textContent = project.total_donations;
            dataRow.appendChild(donationsCell);

            // Append row to table
            table.appendChild(dataRow);
        });

        // Append table to form
        projectsForm.appendChild(table);

        // Open modal
        const modal = new bootstrap.Modal(document.getElementById("projectsModal"));
        modal.show();

        buildAdminTransaction(responseProjects, operationType);
    } catch (error) {
        console.log("Error: ", error);
    }
};


// Send request to server build up admin transaction
function buildAdminTransaction(responseProjects, operationType) {

    let submitTransactionButton = document.getElementById("submitTransactionButton");
    submitTransactionButton.addEventListener("click", async function () {

        try {
            const requestOptions = {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Operation-Type': operationType,
                },
                body: JSON.stringify({ admin_operations: responseProjects })
            };

            let response = await fetch("/build_admin_transaction", requestOptions);
            let data = await response.json();
            let transactionXdr = data.transaction_xdr

            // Sign transaction with Freighter
            let signedTransaction = await signingTransaction(transactionXdr);

            // Send transaction to Stellar
            let hash = await sendTransaction(signedTransaction);

             // Send transaction to Stellar and display hash
            document.getElementById("modalTitle").innerHTML = "Transaction completed!";
            document.getElementById("modalBody").textContent = "Here is your hash:\n" + hash;

            const modal = new bootstrap.Modal(document.getElementById("alertModal"));
            modal.show();

        } catch (error) {
            console.log("Error: ", error);
        };
    });
};


async function teste() {

};
