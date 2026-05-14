FROM golang:1.25

WORKDIR /tests

COPY go.mod go.sum ./
RUN go mod download

COPY . /tests

CMD [ "go", "test", "-race", "-cover", "-v", "./..." ]
