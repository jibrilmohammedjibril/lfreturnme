from fastapi import FastAPI, HTTPException
import schemas
import crud

app = FastAPI()


@app.post("/signup/", response_model=schemas.Signup)
def signup(user: schemas.Signup):
    try:
        db_user = crud.create_user(user=user)
        return db_user
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/signin/") #response_model=schemas.Signin)
def signin(user: schemas.Signin):
    try:
        db_user = crud.authenticate_user(user.email_address, user.password)
        if not db_user:
            raise HTTPException(status_code=400, detail="Invalid email or password")
        return db_user
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")
