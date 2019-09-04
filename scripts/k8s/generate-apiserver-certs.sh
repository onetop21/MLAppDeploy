mkdir -p certs
grep 'client-certificate-data' ~/.kube/config | head -n 1 | awk '{print $2}' | base64 -d >> certs/kubecfg.crt
grep 'client-key-data' ~/.kube/config | head -n 1 | awk '{print $2}' | base64 -d >> certs/kubecfg.key
openssl pkcs12 -export -clcerts -inkey certs/kubecfg.key -in certs/kubecfg.crt -out certs/kubecfg.p12 -name "kubernetes-admin"
cp /etc/kubernetes/pki/ca.crt certs/

cat << EOF > certs/register_win32.bat
@ECHO OFF
set "psCommand=powershell -Command "\$pword = read-host 'Enter Password' -AsSecureString ; ^
    \$BSTR=[System.Runtime.InteropServices.Marshal]::SecureStringToBSTR(\$pword); ^
    [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(\$BSTR)""
for /f "usebackq delims=" %%p in (\`%psCommand%\`) do set PASSWD=%%p
certutil.exe -addstore "Root" ca.crt
certutil.exe -p %PASSWD% -user -importPFX kubecfg.p12
EOF

cat << EOF > certs/register_linux.sh
read -s -p "Enter Password: " PASSWD
sudo apt install -y libnss3-tools
certutil -A -n "Kubernetes" -t "TC,," -d sql:\$HOME/.pki/nssdb -i ca.crt
pk12util -i kubecfg.p12 -d sql:\$HOME/.pki/nssdb -W \$PASSWD 
MOZILLA_PATH=\`find ~/.mozilla/firefox -name "cert8.db" | xargs dirname\`
if [ ! -z \$MOZILLA_PATH ]; then
    certutil -A -n "Kubernetes" -t "TC,," -d \$MOZILLA_PATH -i ca.crt
    pk12util -i kubecfg.p12 \$MOZILLA_PATH -W \$PASSWD 
else
    echo "Cannot find Firefox."
fi
EOF

