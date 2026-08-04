# Deployment

## Local Docker Compose

```bash
docker compose up --build demo-app
```

The demo service is available at `http://localhost:8000`.

Run the test runner image:

```bash
docker compose run --rm test-runner
```

## GitHub Container Registry

Creating a tag such as `v0.1.0` triggers `.github/workflows/publish-image.yml` and publishes:

- `ghcr.io/<owner>/<repo>-runner:<tag>`
- `ghcr.io/<owner>/<repo>-demo:<tag>`

The workflow also updates the `latest` tag.

## Kubernetes

Replace `OWNER` in `deploy/k8s/deployment.yaml`, then run:

```bash
kubectl apply -f deploy/k8s/deployment.yaml
```

For a private GHCR package, configure an image pull secret in the target namespace and reference it from the Deployment.
