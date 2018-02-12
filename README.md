# gke_ci

![Diagram showing deployment pipeline for GKE-CI](./gke_ci.png)

*([Short blog post announcing this project](https://lethain.com/simple-continuous-deployment-on-gke-with-gke-ci/))*

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
cluster over the Kubernetes proxy. First, run kubectl proxy in some other terminal:

    kubectl proxy

Then:

    git clone git@github.com:lethain/gke_ci.git
    virtualen env
    . ./env/bin/activate
    pip install -r requirements
    python ci.py GKE-PROJECT-ID --loc http://localhost:8001

Then trigger a build on Google Container Builder and you're good to go.

## Create a `deployment.yaml`

There are two ways to deploy, either forking the repository and adding `gke_ci` to
your continuous build pipeline, or to checkout the repository, build it once and
upload it to your private registry.

In both cases, you'll need to create a `deployment.yaml` to configure the deployment
and do some setup on Google to create resources:

1. First, you'll need to [create a service account](https://console.cloud.google.com/apis/credentials/serviceaccountkey)
    for consuming the PubSub messages, perhaps name it `service-account-gke-ci`. Give it the 'Pub/Sub Admin' role.
2. Download the secrets for that service account, and upload them:

        kubectl create secret generic gke-ci --from-file ./file-with-secrets.json

3. Create a PubSub Subscriber for the `cloud_builds` topic, name it `gke_ci`.

Finally, create your `deployment.yaml`:

```
apiVersion: extensions/v1beta1
kind: Deployment
metadata:
  name: gke-ci
spec:
  replicas: 1
  template:
    metadata:
      labels:
         app: gke-ci
    spec:
      containers:
        - image: gcr.io/larson-deployment/gke-ci:0.1
          env:
            - name: "GOOGLE_APPLICATION_CREDENTIALS"
              value: "/var/run/secrets/cloud.google.com/file-with-secrets.json"
          volumeMounts:
            - name: "service-account"
              mountPath: "/var/run/secrets/cloud.google.com"
          imagePullPolicy: Always
          name: gke-ci
          command: ["/usr/bin/python"]
          args: ["ci.py", "gke_ci"]
      volumes:
        - name: "service-account"
          secret:
            secretName: gke-ci
```

Then provision it via:

    kubectl apply -f deployment.

After that, you should be good to go!


## CI for your CI

The easiest way to get the container in your private repo is
to make a private fork of this repository,
and then mirror that to Google Source Repository, and actually have `gke_ci`
self-upgrade! I think, conceptually, even in that case it would not miss any
triggering other deploys when it itself upgrades, although that might require
removing the "try-finally" block in the `run` function to fully eliminate the
potential gap).

Anyway, pretty remarkable in my mind to have a CI system that deploy itself!

## Building `Dockerfile` manually

Build the container yourself via
(I've had some trouble getting these instructions work,
I actually deploy using the third method described below):

    export GP="your-project"
    git clone git@github.com:lethain/gke_ci.git
    gcloud docker -a
    docker build -t gcr.io/$GP/gke-ci .
    docker tag CONTAINER_ID gcr.io/$GP/gke-ci:0.1
    gcloud docker -- push gcr.io/$GP/gke-ci

Your deployment should detect the image and upgrade appropriately.