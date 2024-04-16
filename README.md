# Fairgen AI Interview Assignment

This is my implementation project of the requirements specified in Fairgen AI's interview assignment.

I've implemented the project using `fastapi`, hosted with the `uvicorn` ASGI server. It is a simple json-based REST api, with no accompanying frontend. Data storage is via a json file managed by `simplejsondb`. The app has basic user authentication via OAuth2 with JWT tokens, managed by the library `python-jose`. 

## Installation

First, clone the app to your local directory. 

Make sure to change the `secret_key` defined on line 11 of `src/authorization.py` to something more personalized and secure. You can generate a fresh and secure secret key with the command `openssl rand -hex 32`.

The app is designed to run fully dockerized. To deploy it, you will first need `docker` installed on your system. Afterwards, run the following command:

```bash
docker build . -t fairgen-ai-assignment
```

to build the project using the dockerfile in the local directory. This will create a docker image with python 3.9.6 and all the necessary python libraries.

To execute the app, run the following command, depending on your operating system:

in Windows:

```ps1
docker run -p 8000:8000 -v ${PWD}/app_data/:/app/app_data/ fairgen-ai-assignment
```

in Linux:

```bash
docker run -p 8000:8000 -v $(pwd)/app_data/:/app/app_data/ fairgen-ai-assignment
```

This will bind the container to port 8000, and mount the data storage directory within the app to the folder `app_data/` in your local directory. 

## Initial Setup

One requires a user account in order to interact with most of the api. Initially, however, the database does not contain any accounts. You will have to perform a simple bootstrap process in order to create an initial admin account from which you can perform other actions.

First, choose a password for this account. For demonstration purposes, I'll use the text `my-password`, but I would encourage you to choose something more secure.

All endpoints in the api are secured and require an authenticated account to access, with the exception of one: `/hash`. 

Take the password you've chosen, and send a post request to the endpoint `/hash` containing the following json body:

```json
{
  "password": "my-password"
}
```

replacing `my-password` with the password you've chosen.

Here is a sample curl command you can run:

```bash
curl -X POST -H "Content-Type: application/json" -d '{"password":"my-password"}' http://localhost:8000/hash
```

Afterwards, two things should occur:

* You should see a response from the request with a body that looks like the following:

```json
{
  "hashed_password": "$2b$12$2yKFVs2M1Dy7Kfl2AOVoKuVngz66Fp7yW8NOWdaybCaXTIwOkvryq"
}
```

* You should see a new folder & file created in your working directory, at `app_data/database.json`. This is the initial empty database, and its contents should look like this:

```json
{"users": {}, "universities": {}, "rooms": {}, "times": {}}
```

Before making any further changes, stop the docker container running the server.

Next, create the json for a default admin user from the following template:

```json
{
  "id": "1",
  "username": "admin",
  "group": "admin",
  "university": null,
  "hashed_password": "$2b$12$2yKFVs2M1Dy7Kfl2AOVoKuVngz66Fp7yW8NOWdaybCaXTIwOkvryq"
}
```

Make sure you insert the hashed password returned from `/hash` into the `"hashed_password"` field. 

Insert the object into the `"users"` collection of the database file. It should look like this afterwards:

```json
{"users": {
  "1": {
    "id": "1",
    "username": "admin",
    "group": "admin",
    "university": null,
    "hashed_password": "$2b$12$2yKFVs2M1Dy7Kfl2AOVoKuVngz66Fp7yW8NOWdaybCaXTIwOkvryq"
  }
}, "universities": {}, "rooms": {}, "times": {}}
```

Save the database file, and restart the server. You should now be able to acquire a JWT token and log in with this admin account.

## Usage

Since this api is designed without an accompanying frontend, the simplest way to interact with it is via either a utility like Postman, or the built-in swagger documentation provided by fastapi, accessible from the browser by visiting `localhost:8000/docs`. For demonstration purposes, i'll explain how to use the swagger documentation, as that doesn't require the installation of extra tools.

As described above, you can view the swagger documentation by visiting `localhost:8000/docs` in a browser window. As stated earlier, almost all endpoints in the api are authenticated, so you will have to authorize your account via the bootstrapped admin account that you just created.

Click the green "Authorize 🔓" button at the top right of the window, which should open an autorization dialogue. Enter the username `admin` and the password you chose earlier into the "username" and "password" fields, and leave the remaining options at default / blank. Click "Authorize" at the bottom. If successful, the window should change to show that you've been authorized, and the "Authorize" button should change to say "Logout". You can now close this dialogue.

You should now have full access to the api. Explore the various endpoints by expanding them and clicking "Try it out" to manually enter json data, and see formatted json responses.

## Further notes about implementation

This is a fairly minimal implementation of the requirements specified, with plenty of potential improvements one could make to the system. These include:

* Implementation of a proper database system for persistent storage, such as sqlite, mongodb, postgres, or a cloud-hosted solution, such as aws dynamodb or rds.
* Implementation of a cloud hosting and cloud deployment framework, for easy public deployment and scalability.
* Implementation of a proper frontend for interacting with the service.
* Implementation of a unit testing framework.
* Implementation of a more user-friendly user account bootstrapping process.
* Implementation of additional features, such as limitations pertaining to the maximum number of students that may enter a single classroom at once, and estimations for walking times between classrooms.
* Separation of user information updating and password updating operations into separate endpoints.
* Allow the deletion of a range of times between a start and end time.
* Allow variadic specification of fields to modify in `update` requests, as opposed to requiring all of them.
* Implement 'disabled' status for deleted users instead of simply deleting their user entries from the database.
* Websocket events for real-time updates to registered times, sent to clients dynamically

As a final disclaimer: I did use the assistance of LLMS to investigate and choose the tooling and architecture for this project. However, all of the code and language written here in this project and this readme file is my own, or lightly modified from the fastapi documentation (in particular with respect to user authentication). 
