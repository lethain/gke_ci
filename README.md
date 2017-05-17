# gke_ci

Using [Google Container Builder](https://cloud.google.com/container-builder/docs/),
you can go from pushing code to having a new container built and uploaded into
[Google Container Registry](https://cloud.google.com/container-registry/), but
you'll still need to upgrade your deployment manually to point to the new version.

This package automatically updates deployments based on successful Container Builder builds.

The design is fairly simple:

1. it's a Python script that listens to the Google PubSub
    queue named `cloud_builds`, which is populated with status messages by Container Builder
    as it starts and completes builds.
2. When it see messages with a status of `SUCCESS`, it uses the [Kubernetes API](https://kubernetes.io/docs/api-reference/v1.5/#patch-23)
    to `PATCH` the existing deployment configuration to use the new version.

This works well enough, but I'm only using it for my toy software,
so you may want to be a bit more rigorous in your evaluation!

## Run locall via `kubectl proxy`

You can play around with this script by running it locally and accessing your
cluster over the Kubernetes proxy:

    git clone git@github.com:lethain/gke_ci.git
    virtualen env
    . ./env/bin/activate
    pip install -r requirements
    python ci.py GKE-PROJECT-ID --loc http://localhost:8001

Then trigger a build on Google Container Builder and you're good to go.

## Run on GKE

*Still a work in progress, will need to hack together a bit over course of this week, but basically just a Dockerfile and a way to inject a few ENV variables.*

First, we need to build the container and upload it:

    git clone git@github.com:lethain/gke_ci.git
    gcloud preview docker -a
    docker build -t gcr.io/<YOUR PROJECT>/gke_ci .
    docker tag CONTAINER_ID gcr.io/<YOUR PROJECT>/gke_ci:0.1
    gcloud docker -- push gcr.io/<YOUR PROJECT>/gke_ci

Then create a deployment.yaml:

    apiVersion: extensions/v1beta1
    kind: Deployment
    metadata:
      name: gke_ci
    spec:
      replicas: 1
      template:
        metadata:
          labels:
            app: gke_ci
        spec:
          containers:
          - image: gcr.io/<YOUR PROJECT>/gke_ci:0.1
            imagePullPolicy: Always
            name: gke_ci

Then provision it via:

    kubectl apply -f deployment.

After that, you should be good to go!
