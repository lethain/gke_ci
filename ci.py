"""
Simple Google PubSub queue consumer to update Kubernetes.
"""
import sys
import traceback
import copy
import argparse
import pprint
import time
import json
import requests
from collections import defaultdict
from google.cloud import pubsub


def handle(msg, loc, ignore):
    "Handle individual PubSub messages."
    print "handle: %s\n%s" % (msg.data, msg.attributes)
    data = json.loads(msg.data)
    status = msg.attributes['status']
    logUrl = data['logUrl']
    images = data['images']
    repo = data['source']['repoSource']['repoName']
    ks = build_k8s_cli()
    if status == 'SUCCESS':
        print "[%s] Build succeeded." % (repo,)
        all_deployments = deployments(ks, loc, ignore)
        for image in images:
            print "[%s] Updated %s." % (repo, image)
            wo_tag = container_without_tag(image)
            for dep_cont, deps in all_deployments.iteritems():
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
                            headers = copy.deepcopy(ks.headers)
                            headers['Content-Type'] = 'application/strategic-merge-patch+json'
                            r= ks.patch("%s%s" % (loc, dep_link), headers=headers, data=json.dumps(update))
                            print "[%s] %s from %s\n%s" % (repo, r.status_code, r.request.url, r.content)


def container_without_tag(con_str):
    "Return container URL without the tag or preceding colon."
    return ':'.join(con_str.split(':')[:-1])


def deployments(cli, loc, ignore):
    "Build map of containers to deployment configs."
    container_dep = defaultdict(list)
    deps = cli.get("%s/apis/extensions/v1beta1/deployments" % (loc,)).json()['items']
    for dep in deps:
        name = dep['metadata']['name']
        # TODO: add some kind of tag in the deployment to indicate they
        #       should be considered as opposed to defaulting everything in
        if dep['metadata']['namespace'] in ignore:
            continue
        print 'found deployment: %s' % (name,)
        containers = dep['spec']['template']['spec']['containers']
        for container in containers:
            img = container_without_tag(container['image'])
            container_dep[img].append(dep)
    return container_dep


def build_k8s_cli():
    "Setup authenticated Kubernetes API client."
    s = requests.Session()
    s.verify = '/var/run/secrets/kubernetes.io/serviceaccount/ca.crt'
    try:
        creds = open('/var/run/secrets/kubernetes.io/serviceaccount/token', 'r').read()
        s.headers = {'Authorization': 'Bearer %s' % creds}
    except:
        pass
    return s


def run(loc, project, ignore, delay):
    "Loop endlessly checking for builds."
    print "getting started listening on %s" % (project,)
    while True:
        client = pubsub.Client()
        topic = client.topic('cloud_builds')
        s = pubsub.subscription.Subscription(project, topic=topic)
        pulled = s.pull(max_messages=1)
        for ack_id, message in pulled:
            try:
                handle(message, loc, ignore)
                s.acknowledge([ack_id])
            except Exception, e:
                print "failed handling: %s\nattrs: %s\ndata: %s" % (e, message.attributes, message.data)
                ex_type, ex, tb = sys.exc_info()
                traceback.print_tb(tb)
                del tb

        time.sleep(delay)


def main():
    "Parse args, start the program."
    p = argparse.ArgumentParser(description='Continuous integration for GKE.')
    p.add_argument('project', help='name of GCE project')
    p.add_argument('--loc', default='https://kubernetes', help='location to access Kubernetes API')
    p.add_argument('--delay', type=int, default=15.0, help='delay between checking for messages')
    p.add_argument('--ignore', default='kube-system', help='csv of namespaces to ignore')
    args = p.parse_args()
    run(args.loc, args.project, args.ignore.split(','), args.delay)


if __name__ == "__main__":
    main()
