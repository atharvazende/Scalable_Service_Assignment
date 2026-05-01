import yaml

with open('k8s/services.yaml', 'r') as f:
    docs = list(yaml.safe_load_all(f))

for doc in docs:
    if doc and doc.get('kind') == 'Deployment':
        container = doc['spec']['template']['spec']['containers'][0]
        port = container['ports'][0]['containerPort']
        
        container['livenessProbe'] = {
            'httpGet': {'path': '/health', 'port': port},
            'initialDelaySeconds': 5,
            'periodSeconds': 10
        }
        container['readinessProbe'] = {
            'httpGet': {'path': '/health', 'port': port},
            'initialDelaySeconds': 5,
            'periodSeconds': 10
        }
        container['resources'] = {
            'requests': {'memory': '64Mi', 'cpu': '100m'},
            'limits': {'memory': '256Mi', 'cpu': '500m'}
        }
        
        new_env = [
            {'name': 'DB_USER', 'valueFrom': {'configMapKeyRef': {'name': 'eci-config', 'key': 'POSTGRES_USER'}}},
            {'name': 'DB_PASS', 'valueFrom': {'secretKeyRef': {'name': 'eci-secret', 'key': 'POSTGRES_PASSWORD'}}}
        ]
        
        for env_var in container.get('env', []):
            if env_var['name'] == 'DATABASE_URL':
                db_name = env_var['value'].split('/')[-1]
                env_var['value'] = f'postgresql://$(DB_USER):$(DB_PASS)@postgres:5432/{db_name}'
            new_env.append(env_var)
            
        container['env'] = new_env

with open('k8s/services.yaml', 'w') as f:
    yaml.dump_all(docs, f, sort_keys=False)
