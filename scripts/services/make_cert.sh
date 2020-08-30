#!/bin/bash
docker run -it --name golang --rm -v ${HOME}/.mlad/.services/minio-config/certs/CAs/:/out golang /bin/bash -c "wget -O generate_cert.go https://golang.org/src/crypto/tls/generate_cert.go?m=text; go run generate_cert.go -ca --host s3.amazonaws.com;cp cert.pem /out/public.crt;cp key.pem /out/private.key"
