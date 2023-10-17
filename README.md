# Lux Crowdfunding Platform

## Overview

Lux is an ongoing project designed to facilitate crowdfunding via the Stellar blockchain. It exclusively operates on Stellar's TESTNET network, offering a seamless experience for project creators and backers alike.

## Technologies

- **Backend**: Python and Flask.
- **Frontend**: HTML, Jinja, and Bootstrap.
- **Database**: MySQL (RDS).
- **Storage**: Amazon S3.

## Preparation

To create a Stellar account with Freighter, access https://www.freighter.app/, install the extension and follow the tutorial. After you log in on your account in the extension, make sure to swap to Testnet.

## Getting Started

1. Make sure you have Python installed.

2. Install a self signed SSL certificate.

3. Clone the repository:
`git clone https://github.com/giuliannarlau/crowdfunding.git`.

4. Create a new virtual environment, executing the follow:
`python -m venv venv`

5. Activate the environment:
   - **Windows**: `.\venv\Scripts\activate`
   - **macOS and Linux**: `source venv/bin/activate`

6. Install the required packages: 
`pip install -r requirements.txt`.

7. Set up your environment variables:
   - Copy the `.env.sample` file to a new file named `.env`.
   - Fill in the appropriate values for your S3, RDS, and other required configurations in the `.env` file.

8. Start the Flask application: `flask run`.


## Contributing

This project welcomes contributions. Please feel free to submit pull requests or raise issues.

## License

Licensed under the MIT License. See the [License](LICENSE.txt) file for more details.

