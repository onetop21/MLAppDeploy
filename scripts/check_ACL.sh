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

function CheckPort {
    RESULT=0
    for PORT in $@
    do
        if [[ -n $TCP && $TCP -eq 1 ]]; then
            nc -z -v -w 10 $ADDRESS $PORT > /dev/null 2>&1
            let "RESULT |= $?"
        fi
        if [[ -n $UDP && $UDP -eq 1 ]]; then
            nc -z -v -u -w 10 $ADDRESS $PORT > /dev/null 2>&1
            let "RESULT |= $?"
        fi
    done
    return $RESULT
}

printf "Check to $ADDRESS...\n"

printf "Checking Docker Remote Port(HTTP)..."
TCP=1 CheckPort 2375 
PrintResult
printf "Checking Docker Remote Port(HTTPS)..."
TCP=1 CheckPort 2376 
PrintResult
printf "Checking Docker Swarm Port..."
TCP=1 CheckPort 2377 
PrintResult
printf "Checking Docker Discovery Communication Port..."
TCP=1 UDP=1 CheckPort 7946 
PrintResult
printf "Checking Docker Overlay Network Port..."
UDP=1 CheckPort 4789 
PrintResult

