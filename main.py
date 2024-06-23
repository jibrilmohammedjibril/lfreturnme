from fastapi import FastAPI, HTTPException
import schemas
import crud

app = FastAPI()


@app.post("/signup/", response_model=schemas.ResponseSignup)
def signup(user: schemas.Signup):
    try:
        db_user = crud.create_user(user=user)
        if db_user:
            return db_user
        else:
            raise HTTPException(status_code=400, detail="Email address already exists")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/signin/")  #response_model=schemas.Signin)
def signin(email_address: str, password: str):
    try:
        db_user = crud.authenticate_user(email_address, password)
        print(db_user)
        if not db_user:
            #print("invalid email or password")
            raise HTTPException(status_code=400, detail="Invalid email or password")
        return db_user
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid email or password2")
        #raise HTTPException(status_code=500, detail="Internal server error")
