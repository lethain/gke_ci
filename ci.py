"""
Simple Google PubSub queue consumer to update Kubernetes.
"""
import copy
import argparse
import pprint
import time
import json
import requests
from collections import defaultdict
from google.cloud import pubsub


def handle(msg, loc, ignore):
    print msg.attributes
    data = json.loads(msg.data)
    status = msg.attributes['status']
    logUrl = data['logUrl']
    images = data['images']
    repo = data['source']['repoSource']['repoName']
    ks = build_k8s_cli()
    if status == 'SUCCESS':
        print "[%s] Build succeeded." % (repo,)
        deps = deployments(ks, loc, ignore)
        for image in images:
            print "[%s] Updated %s." % (repo, image)
            wo_tag = container_without_tag(image)
            for dep_cont, deps in deps.iteritems():
                for dep in deps:
                    if wo_tag == dep_cont:
                        changed = False
                        dep_link = dep['metadata']['selfLink']
                        curr_containers = copy.deepcopy(dep['spec']['template']['spec']['containers'])
                        for curr_cont in curr_containers:
                            old_image = curr_cont['image']
                            if old_image.startswith(dep_cont):
                                print "[%s] Upgrading from %s to use %s" % (repo, old_image, image)
                                curr_cont['image'] = image
                                changed = True

                        if changed:
                            update = {"spec": {"template": {"spec": {"containers": curr_containers}}}}
                            headers = {'Content-Type': 'application/strategic-merge-patch+json'}
                            r= ks.patch("%s%s" % (loc, dep_link), headers=headers, data=json.dumps(update))
                            print "[%s] %s from %s\n%s" % (repo, r.status_code, r.request.url, r.content)


def container_without_tag(con_str):
    "Return container URL without the tag or preceding colon."
    return ':'.join(con_str.split(':')[:-1])


def deployments(cli, loc, ignore):
    container_dep = defaultdict(list)
    deps = cli.get("%s/apis/extensions/v1beta1/deployments" % (loc,)).json()['items']
    for dep in deps:
        name = dep['metadata']['name']
        # TODO: add some kind of tag in the deployment to indicate
        #       they should be considered as opposed to defaulting
        #       everything in
        if dep['metadata']['namespace'] in ignore:
            continue

        print 'found deployment: %s' % (name,)
        containers = dep['spec']['template']['spec']['containers']
        for container in containers:
            img = container_without_tag(container['image'])
            container_dep[img].append(dep)
    return container_dep


def build_k8s_cli():
    s = requests.Session()
    s.verify = '/var/run/secrets/kubernetes.io/serviceaccount/ca.crt'
    return s
#return lambda method, path : s.request(method, "%s%s" % (loc, path))


def run(loc, project, ignore, delay):
    "Loop endlessly checking for builds."
    client = pubsub.Client()
    topic = client.topic('cloud_builds')
    s = pubsub.subscription.Subscription(project, topic=topic)
    while True:
        pulled = s.pull(max_messages=10)
        for ack_id, message in pulled:
            try:
                handle(message, loc, ignore)
            finally:
                s.acknowledge([ack_id])
        time.sleep(delay)



def main():
    p = argparse.ArgumentParser(description='Continuous integration for GKE.')
    p.add_argument('project', help='name of GCE project')
    p.add_argument('--loc', default='https://kubernetes', help='location to access Kubernetes API')
    p.add_argument('--delay', type=int, default=1.0, help='delay between checking for messages')
    p.add_argument('--ignore', default='kube-system', help='csv of namespaces to ignore')
    args = p.parse_args()
    run(args.loc, args.project, args.ignore.split(','), args.delay)


if __name__ == "__main__":
    main()
