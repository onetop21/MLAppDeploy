#!/bin/bash

service nginx start
./minio gateway s3 $S3_ENDPOINT --console-address ":9001"
#MINIO_BROWSER=false ./minio gateway s3 $S3_ENDPOINT &
#CONSOLE_SECURE_FRAME_DENY=off ./console server --port 9001