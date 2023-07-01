#!/bin/bash

if [ "$API_DEBUG" = "True" ]; then
    echo "Running Development Server"
    uvicorn main:app --reload --host 0.0.0.0 --port $API_PORT
else
    echo "Running Production Server"
    uvicorn main:app --host 0.0.0.0 --port $API_PORT
fi