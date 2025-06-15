# Data Recording README

## Build Artifact
```
mvn clean install -Pproduction
```

## Build image
```bash
docker build -t mohadipe/data-recording:0.0.1-SNAPSHOT .
```

## Run Docker image
```bash
docker-compose up -d
```

## Stop Docker image
```bash
docker-compose down
```

## Vaadin Getting Started

The [Getting Started](https://vaadin.com/docs/latest/getting-started) guide will quickly familiarize you with your new
Data Recording implementation. You'll learn how to set up your development environment, understand the project 
structure, and find resources to help you add muscles to your skeleton — transforming it into a fully-featured 
application.
