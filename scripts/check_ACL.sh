if [ -z $1 ]; then
    read -p "Target IP Address : " ADDRESS
else
    ADDRESS=$1
fi

function PrintResult {
    if [ $? == 0 ]; then
        echo -e "\033[32m[SUCCEED]\033[0m"
    else
        echo -e "\033[31m[FAILED]\033[0m"
    fi
}

printf "Check to $ADDRESS...\n"

printf "Checking Docker Remote Port(HTTP)..."
nc -z -v $ADDRESS 2375 > /dev/null 2>&1
PrintResult
printf "Checking Docker Remote Port(HTTPS)..."
nc -z -v $ADDRESS 2376 > /dev/null 2>&1
PrintResult
printf "Checking Docker Swarm Port..."
nc -z -v $ADDRESS 2377 > /dev/null 2>&1
PrintResult
printf "Checking Docker Discovery Communication Port..."
nc -z -v $ADDRESS 7946 > /dev/null 2>&1
nc -z -v -u $ADDRESS 7946 > /dev/null 2>&1
PrintResult
printf "Checking Docker Overlay Network Port..."
nc -z -v -u $ADDRESS 4789 > /dev/null 2>&1
PrintResult

