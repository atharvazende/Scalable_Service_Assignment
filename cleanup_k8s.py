import yaml

with open('k8s/services.yaml', 'r') as f:
    docs = list(yaml.safe_load_all(f))

for doc in docs:
    if doc and doc.get('kind') == 'Deployment':
        container = doc['spec']['template']['spec']['containers'][0]
        
        # Deduplicate env vars by name
        unique_env = {}
        for env_var in container.get('env', []):
            if env_var['name'] not in unique_env:
                unique_env[env_var['name']] = env_var
                
        # Ensure DB_USER and DB_PASS exist
        unique_env['DB_USER'] = {'name': 'DB_USER', 'valueFrom': {'configMapKeyRef': {'name': 'eci-config', 'key': 'POSTGRES_USER'}}}
        unique_env['DB_PASS'] = {'name': 'DB_PASS', 'valueFrom': {'secretKeyRef': {'name': 'eci-secret', 'key': 'POSTGRES_PASSWORD'}}}
        
        container['env'] = list(unique_env.values())

with open('k8s/services.yaml', 'w') as f:
    yaml.dump_all(docs, f, sort_keys=False)
