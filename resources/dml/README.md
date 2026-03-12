```bash
jf rt dl alexsh-generic-local/PyYAML-5.2-cp27-cp27m-win32.whl --server-id local


# [Prpoerty to be set](https://jfrog.com/help/r/jfrog-rest-apis/set-item-properties) by TML  
# http://localhost:8046/artifactory/api/storage/alexsh-generic-local/PyYAML-5.2-cp27-cp27m-win32.whl

APPROVED=true && curl --location --request PUT "http://localhost:8080/artifactory/api/storage/alexsh-generic-local/PyYAML-5.2-cp27-cp27m-win32.whl?properties=approved=${APPROVED}" \
--header "Authorization: Bearer ${BEARER_TOKEN}"
```