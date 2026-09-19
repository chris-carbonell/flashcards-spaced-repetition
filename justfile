# global variables
project := "spaced-repetition"
name := "spaced-repetition"
version := "v1.0.0"
registry := "zot.carbo"
image_tag := project + "-" + name + ":" + version
image_uri := registry + "/" + project + "/" + name + ":" + version

# build the local image
build:
    docker build -f build/Dockerfile -t {{name}}:{{version}} build

# tag the image for the local registry
tag:
    docker tag {{name}}:{{version}} {{image_uri}}

# push to Zot
push:
    docker push {{image_uri}}

# do everything
release: build tag push

# run locally with docker compose
run:
    docker compose up --build