# Deployment Instructions for filemanager service

To install the filemanager service to the development namespace in the
kubernetes cluster:


```bash
helm install ./ --name=filemanager --set=image.tag=564f852 \
  --tiller-namespace=development --namespace=development \
  --set=vault.enabled=1 --set=vault.port=8200  \
  --set=vault.host=<VAULT_HOST_IP> \
  --set=database.host=<FILEMANAGER_DB_HOST> \
  --set=scaling.replicas=1
```

This assumes that the requisite Vault roles and policies have already been installed.

To delete the pod, run:
```
helm del --purge filemanager --tiller-namespace=development
```
