
// Check and uncheck all checkboxes
function selectAll(source) {
    // TODO: handle when user checks/unchecks all after selecting one ore more projects

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
        const responseFund = await fetch("/control_panel", {
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

