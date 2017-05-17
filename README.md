# gke_ci

Using [Google Container Builder](https://cloud.google.com/container-builder/docs/),
you can go from pushing code to having a new container built and uploaded into
[Google Container Registry](https://cloud.google.com/container-registry/), but
you'll still need to upgrade your deployment yourself.

Fortunately, Container Builder publishes events into Google PubSub for each build
into a queue named:

    projects/$PROJECT-NAME/topics/cloud-builds

and you can add a Kubernetes deployment runs a single pod, which subscribes to those
events and triggers updates.

This is very much a sketch, not at all a quality solution!

## Run Locally

You can play around with this script by running it locally and accessing your
cluster over the Kubernetes proxy:

    git clone <>
    virtualen env
    . ./env/bin/activate
    pip install -r requirements
    python ci.py GKE-PROJECT-ID --loc http://localhost:8001 

Then trigger a build on Google Container Builder and you're good to go.

## Run on GKE


Generally approach is:

1. Checkout this repo.
2. Build a copy for your local container store:

        docker build somehow

3. Upload the container to your private repo:

        blah blah blah

4. Add a subscription in [Google PubSub](https://console.cloud.google.com/cloudpubsub/topicList) named `gke_ci`.
5. Create a deployment which sets these variables in a file named `gke_ci_deploy.yaml`:

    etc

6. Deploy it:

    kubectl apply -f deployment.

7. Deploy some new changes, and see it work! If it doesn't look at the logs.
