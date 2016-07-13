# encoding=utf-8
import httplib
import urllib
import json
import threading
from datetime import datetime, timedelta

NEXUS_URL = '127.0.0.1:8080'


class ConnectionPool(object):

    def __init__(self, host, size=10):
        self.host = host
        self.size = size
        self.initial_size = size
        self.connections = {}
        self.lock = threading.Lock()
        self.initialize()

    def initialize(self):

        for i in range(self.size):
            conn = httplib.HTTPConnection(self.host)
            self.connections[conn] = False

    def get_connection(self):
        self.lock.acquire()
        try:
            for c, used in self.connections.items():
                if not used:
                    self.connections[c] = True
                    return c
            # If we got there we should increase pool
            new_conn = httplib.HTTPConnection(self.host)
            self.connections[new_conn] = True
            self.size += 1
            return new_conn
        finally:
            self.lock.release()
        return None

    def __clean(self):
        need_clean = len(self.connections) - self.initial_size
        if need_clean > 0:
            cleaned = need_clean
            for c, used in self.connections.items():
                if cleaned <= 0:
                    break
                if not used:
                    c.close()
                    del self.connections[c]
                    cleaned -= 1
                    self.size -= 1

    def put_connection(self, connection):
        self.lock.acquire()
        try:
            self.connections[connection] = False
            self.__clean()
        finally:
            self.lock.release()

    def reconnect(self, connection):
        connection.close()
        self.lock.acquire()
        try:
            for c, used in self.connections.items():
                if not used:
                    c.close()
        finally:
            self.lock.release()

    @classmethod
    def get_instance(cls, host, size=10):
        if not hasattr(cls, "__POOL_INSTANCE__"):
            cls.__POOL_INSTANCE__ = {}
        if host not in cls.__POOL_INSTANCE__:
            cls.__POOL_INSTANCE__[host] = ConnectionPool(host, size)
        return cls.__POOL_INSTANCE__[host]


class AbstractNexusConnection:

    def __init__(self, token=None):
        self.host = NEXUS_URL
        self.token = token
        self.pool = ConnectionPool.get_instance(NEXUS_URL)

    def login(self, username, password):
        try:
            data = self.request('POST', '/api/v2/login',
                                {'username': username, 'password': password})
            return data
        except Exception as e:
            return False

    def request_token(self, method, path, params={}):
        emessage = ""
        params['token'] = self.token
        for i in range(3):
            try:
                return self.request(method, path, params)
            except Exception, e:
                emessage = unicode(e)
        raise Exception(emessage)

    def request(self, method, path, params={}):
        params_str = urllib.urlencode(params)
        conn = self.pool.get_connection()
        headers = {}
        headers['User-Agent'] = 'Nexus API'
        headers['Accept'] = "*/*"
        if method == 'POST':
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        try:
            conn.request(method, path, params_str, headers)
            resp = conn.getresponse()
            rdata = resp.read()
            data = json.loads(rdata)
            if resp.status != 200:
                raise Exception(rdata)
            return data
        except httplib.HTTPException, e:
            # If we got some bad data, maybe there has some error now.
            # so if we use connection pool, we should close the connection
            # and make it reconnect in next time.
            self.pool.reconnect(conn)
            raise e
        finally:
            self.pool.put_connection(conn)


class CloudAPIConnection(AbstractNexusConnection):

    def validation_token(self):
        data = self.request_token('POST', '/api/v2/validation_token')
        return data

    # Misc APIs
    def logout(self):
        data = self.request_token('POST', '/api/v2/logout')
        return data

    def change_password(self, old_password, new_password):
        params = {
            "old": old_password,
            "new": new_password
        }
        data = self.request_token('POST', '/api/v2/change_login_password', params)
        return data

    def status(self):
        data = self.request_token('POST', '/api/v2/status')
        return data

    def list_datacenter(self):
        data = self.request_token('POST', '/api/v2/datacenters')
        return data

    def list_image(self, names=None):
        params = {}
        if names:
            params['names'] = names
        data = self.request_token('POST', '/api/v2/images', params)
        return data

    def show_image(self, name):
        data = self.request_token('POST', '/api/v2/images', {'name': name})
        return data

    def list_isps(self):
        data = self.request_token('POST', '/api/v2/isps')
        return data

    def bill(self):
        data = self.request_token('POST', '/api/v2/bills')
        return data

    def destroy_image(self, name):
        data = self.request_token(
            'POST', '/api/v2/images/destroy', {'name': name})
        return data

    def update_comments(self, name, comments):
        data = self.request_token(
            'POST', '/api/v2/images/update_comments', {'name': name, 'comments': comments})
        return data

    # Network APIs
    def list_networks(self, ids=None):
        params = {}
        if ids is not None:
            params['ids'] = ids
        data = self.request_token('POST', '/api/v2/networks', params)
        return data

    def show_network(self, nid):
        data = self.request_token('POST', '/api/v2/networks', {'id': nid})
        return data

    def create_network(self, data_center):
        data = self.request_token(
            'POST', '/api/v2/network/create', {'datacenter': data_center})
        return data

    def delete_network(self, nid):
        data = self.request_token(
            'POST', '/api/v2/network/delete', {'id': nid})
        return data

    def ip_already_in_used(self, nid, ip):
        data = self.request_token(
            'POST', '/api/v2/network/ip_already_in_used', {'id': nid, 'ip': ip})
        return data['result']

    # Security Group API
    def create_security_group(self, comments):
        data = self.request_token(
            'POST', '/api/v2/security_group/create', {'comments': comments})
        return data

    def list_security_groups(self):
        data = self.request_token('POST', '/api/v2/security_groups')
        return data

    def show_security_group(self, sgid):
        data = self.request_token(
            'POST', '/api/v2/security_groups', {'ids': sgid})
        return data

    def delete_security_group(self, sgid):
        data = self.request_token(
            'POST', '/api/v2/security_group/delete', {'id': sgid})
        return data

    def update_security_group(self, sgid, comments=None, ingress=None, outgress=None, need_update=False):
        params = {'id': sgid}
        if comments is not None:
            params['comments'] = comments
        if ingress is not None:
            params['ingress'] = json.dumps(ingress)
        if outgress is not None:
            params['outgress'] = json.dumps(outgress)
        if need_update:
            params['need_update'] = 1
        data = self.request_token(
            'POST', '/api/v2/security_group/update', params)
        return data

    # Server APIs
    def vm_has_enough_resource(self, params):
        data = self.request_token(
            'POST', '/api/v2/server/has_enough_resource', params)
        return data

    def list_servers(self, all_server=False, ids=None):
        params = {}
        if all_server:
            params['all'] = 'true'
        if ids:
            params['ids'] = ids
        data = self.request_token('POST', '/api/v2/servers', params)
        for server in data:
            self._fix_stopped_status(server)
        return data

    def set_metadata(self, sid, metadata):
        data = self.request_token(
            'POST', '/api/v2/server/set_metadata', {'id': sid, 'metadata': metadata})
        return data

    def show_server(self, sid):
        data = self.request_token('POST', '/api/v2/servers', {'id': sid})
        self._fix_stopped_status(data)
        return data

    def _fix_stopped_status(self, data):
        if 'status' in data and data['status'] == 'Stoped':
            data['status'] = 'Stoped'

    def jobs(self, sid):
        data = self.request_token('POST', '/api/v2/server/jobs', {'id': sid})
        return data

    def provision(self, params):
        data = self.request_token('POST', '/api/v2/server/provision', params)
        return data

    def toggle_private_network(self, sid):
        data = self.request_token(
            'POST', '/api/v2/server/toggle_private_network', {'id': sid})
        return data

    def resize_server(self, sid, params):
        params['id'] = sid
        data = self.request_token('POST', '/api/v2/server/resize', params)
        return data

    def destroy_server(self, sid):
        data = self.request_token(
            'POST', '/api/v2/server/destroy', {'id': sid})
        return data

    def direct_destroy_server(self, sid):
        data = self.request_token(
            'POST', '/api/v2/server/direct_destroy', {'id': sid})
        return data

    def start_server(self, sid):
        data = self.request_token('POST', '/api/v2/server/start', {'id': sid})
        return data

    def stop_server(self, sid):
        data = self.request_token('POST', '/api/v2/server/stop', {'id': sid})
        return data

    def shutdown_server(self, sid):
        data = self.request_token(
            'POST', '/api/v2/server/shutdown', {'id': sid})
        return data

    def restart_server(self, sid):
        data = self.request_token(
            'POST', '/api/v2/server/restart', {'id': sid})
        return data

    def suspend_server(self, sid):
        data = self.request_token(
            'POST', '/api/v2/server/suspend', {'id': sid})
        return data

    def resume_server(self, sid):
        data = self.request_token('POST', '/api/v2/server/resume', {'id': sid})
        return data

    def change_image(self, sid, image):
        data = self.request_token(
            'POST', '/api/v2/server/change_image', {'id': sid, 'image': image})
        return data

    def set_password(self, sid, password):
        data = self.request_token(
            'POST', '/api/v2/server/set_password', {'id': sid, 'password': password})
        return data

    def set_tags(self, sid, tags):
        data = self.request_token(
            'POST', '/api/v2/server/set_tags', {'id': sid, 'tags': tags})
        return data

    def show_job(self, jid):
        data = self.request_token('POST', '/api/v2/server/job', {'id': jid})
        return data

    def list_backups(self, sid):
        data = self.request_token(
            'POST', '/api/v2/server/backups', {'id': sid})
        return data

    def backup(self, sid, name):
        data = self.request_token(
            'POST', '/api/v2/server/backup/create', {'id': sid, 'name': name})
        return data

    def restore(self, sid, name):
        data = self.request_token(
            'POST', '/api/v2/server/backup/restore', {'id': sid, 'name': name})
        return data

    def delete_backup(self, sid, name):
        data = self.request_token(
            'POST', '/api/v2/server/backup/delete', {'id': sid, 'name': name})
        return data

    def attach_volume(self, sid, volume):
        data = self.request_token(
            'POST', '/api/v2/server/attach', {'id': sid, 'volume': volume})
        return data

    def detach_volume(self, sid, volume):
        data = self.request_token(
            'POST', '/api/v2/server/detach', {'id': sid, 'volume': volume})
        return data

    def console_data(self, sid):
        data = self.request_token(
            'POST', '/api/v2/server/console_data', {'id': sid})
        return data

    def create_image(self, sid, comments):
        data = self.request_token(
            'POST', '/api/v2/server/create_image', {'id': sid, 'comments': comments})
        return data

    def network_list(self, sid):
        data = self.request_token(
            'POST', '/api/v2/server/network_list', {'id': sid})
        return data

    def join_network(self, sid, nid):
        data = self.request_token(
            'POST', '/api/v2/server/join', {'id': sid, 'network_id': nid})
        return data

    def leave_network(self, sid, nid):
        data = self.request_token(
            'POST', '/api/v2/server/leave', {'id': sid, 'network_id': nid})
        return data

    def apply_security_group(self, sid, sgid, replace=False):
        replace_str = "0"
        if replace:
            replace_str = "1"
        data = self.request_token('POST', '/api/v2/server/security_group/apply',
                                  {'id': sid, 'security_group_id': sgid, 'replace': replace_str})
        return data

    def leave_security_group(self, sid, sgid):
        data = self.request_token('POST', '/api/v2/server/security_group/leave',
                                  {'id': sid, 'security_group_id': sgid})
        return data

    # Volume APIs
    def show_volume_job(self, jid):
        data = self.request_token('POST', '/api/v2/volume/job', {'id': jid})
        return data

    def list_volumes(self, all_volume=False, names=None):
        params = {}
        if all_volume:
            params['all'] = 'true'
        if names:
            params['names'] = names
        data = self.request_token('POST', '/api/v2/volumes', params)
        return data

    def show_volume(self, name):
        data = self.request_token('POST', '/api/v2/volumes', {'name': name})
        return data

    def create_volume(self, data_center, size, tags, cluster=None, ioparams={}):
        params = {'size': size, 'tags': tags, 'datacenter': data_center}
        if cluster:
            params['cluster'] = cluster
        params.update(ioparams)
        data = self.request_token('POST', '/api/v2/volume/create', params)
        return data

    def delete_volume(self, name):
        data = self.request_token(
            'POST', '/api/v2/volume/delete', {'name': name})
        return data

    def set_volume_tags(self, name, tags):
        data = self.request_token(
            'POST', '/api/v2/volume/set_tags', {'name': name, 'tags': tags})
        return data

    def list_snapshots(self, volume):
        data = self.request_token(
            'POST', '/api/v2/volume/snapshots', {'name': volume})
        return data

    def create_snapshot(self, snapshot_name):
        data = self.request_token(
            'POST', '/api/v2/volume/snapshot/create', {'name': snapshot_name})
        return data

    def rollback_snapshot(self, snapshot_name):
        data = self.request_token(
            'POST', '/api/v2/volume/snapshot/rollback', {'snapshot': snapshot_name})
        return data

    def delete_snapshot(self, snapshot_name):
        data = self.request_token(
            'POST', '/api/v2/volume/snapshot/delete', {'snapshot': snapshot_name})
        return data

    def volume_jobs(self, name):
        data = self.request_token(
            'POST', '/api/v2/volume/jobs', {'name': name})
        return data

    def resize_volume(self, name, size):
        data = self.request_token(
            'POST', '/api/v2/volume/resize', {'name': name, 'size': size})
        return data

    # Load Balancers API
    def lb_has_enough_resource(self, params):
        data = self.request_token(
            'POST', '/api/v2/loadbalancers/has_enough_resource', params)
        return data

    def lb_provision(self, config):
        data = self.request_token(
            'POST', '/api/v2/loadbalancers/provision', config)
        return data

    def lb_details(self, id):
        data = self.request_token('POST', '/api/v2/loadbalancers', {'id': id})
        return data

    def lb_list(self, all_lbs=False, ids=None):
        params = {}
        if all_lbs:
            params['all'] = 'true'
        if ids:
            params['ids'] = ids
        data = self.request_token('POST', '/api/v2/loadbalancers', params)
        return data

    def lb_jobs(self, id):
        data = self.request_token(
            'POST', '/api/v2/loadbalancers/jobs', {'id': id})
        return data

    def lb_show_job(self, jid):
        data = self.request_token(
            'POST', '/api/v2/loadbalancers/job', {'id': jid})
        return data

    def lb_start(self, id):
        data = self.request_token(
            'POST', '/api/v2/loadbalancers/start', {'id': id})
        return data

    def lb_stop(self, id):
        data = self.request_token(
            'POST', '/api/v2/loadbalancers/stop', {'id': id})
        return data

    def lb_reload(self, id):
        data = self.request_token(
            'POST', '/api/v2/loadbalancers/reload', {'id': id})
        return data

    def lb_resize(self, id, bandwidth):
        params = {'id': id, 'bandwidth': bandwidth}
        data = self.request_token(
            'POST', '/api/v2/loadbalancers/resize', params)
        return data

    def lb_destroy(self, id):
        data = self.request_token(
            'POST', '/api/v2/loadbalancers/destroy', {'id': id})
        return data

    def lb_add_application(self, id, config):
        config['id'] = id
        data = self.request_token(
            'POST', '/api/v2/loadbalancers/applications/add', config)
        return data

    def lb_update_application(self, id, appid, config):
        config['id'] = id
        config['appid'] = appid
        data = self.request_token(
            'POST', '/api/v2/loadbalancers/applications/update', config)
        return data

    def lb_delete_application(self, id, appid):
        params = {'id': id, 'appid': appid}
        data = self.request_token(
            'POST', '/api/v2/loadbalancers/applications/delete', params)
        return data

    def get_cloud_server_databases_backend(self, id):
        data = self.request_token(
            'POST', '/api/v2/loadbalancers/get_cloud_server_databases_backend', {'id': id})
        return data

    def lb_add_backend(self, id, config):
        config['id'] = id
        data = self.request_token(
            'POST', '/api/v2/loadbalancers/backends/add', config)
        return data

    def lb_update_backend(self, id, backid, config):
        config['id'] = id
        config['backid'] = backid
        data = self.request_token(
            'POST', '/api/v2/loadbalancers/backends/update', config)
        return data

    def lb_delete_backend(self, id, backid):
        params = {'id': id, 'backid': backid}
        data = self.request_token(
            'POST', '/api/v2/loadbalancers/backends/delete', params)
        return data

    def lb_networks(self, id):
        data = self.request_token(
            'POST', '/api/v2/loadbalancers/networks', {'id': id})
        return data

    def lb_network_list(self, id):
        data = self.request_token(
            'POST', '/api/v2/loadbalancers/networks_list', {'id': id})
        return data

    def lb_join_network(self, id, network_id, config):
        config['id'] = id
        config['network_id'] = network_id
        data = self.request_token(
            'POST', '/api/v2/loadbalancers/networks/join', config)
        return data

    def lb_rejoin_network(self, id, network_id, config):
        config['id'] = id
        config['network_id'] = network_id
        data = self.request_token(
            'POST', '/api/v2/loadbalancers/networks/rejoin', config)
        return data

    def lb_leave_network(self, id, network_id):
        config = {
            'id': id,
            'network_id': network_id,
        }
        data = self.request_token(
            'POST', '/api/v2/loadbalancers/networks/leave', config)
        return data

    def lb_toggle_private_network(self, id):
        data = self.request_token(
            'POST', '/api/v2/loadbalancers/toggle_private_network', {'id': id})
        return data

    # Router API
    def rt_has_enough_resource(self, params):
        return self.request_token('POST', '/api/v2/routers/has_enough_resource', params)

    def rt_provision(self, config):
        return self.request_token('POST', '/api/v2/routers/provision', config)

    def rt_list(self, all_dbs=False, ids=None):
        params = {}
        if all_dbs:
            params['all'] = 'true'
        if ids:
            params['ids'] = ids
        return self.request_token('POST', '/api/v2/routers', params)

    def rt_details(self, id):
        return self.request_token('POST', '/api/v2/routers', {'id': id})

    def rt_jobs(self, id):
        return self.request_token('POST', '/api/v2/routers/jobs', {'id': id})

    def rt_show_job(self, jid):
        return self.request_token('POST', '/api/v2/routers/job', {'id': jid})

    def rt_start(self, id):
        return self.request_token('POST', '/api/v2/routers/start', {'id': id})

    def rt_stop(self, id):
        return self.request_token('POST', '/api/v2/routers/stop', {'id': id})

    def rt_reload(self, id):
        return self.request_token('POST', '/api/v2/routers/reload', {'id': id})

    def rt_resize(self, id, bandwidth):
        params = {'id': id, 'bandwidth': bandwidth}
        return self.request_token('POST', '/api/v2/routers/resize', params)

    def rt_destroy(self, id):
        return self.request_token('POST', '/api/v2/routers/destroy', {'id': id})

    def rt_toggle_private_network(self, id):
        return self.request_token('POST', '/api/v2/routers/toggle_private_network', {'id': id})

    def rt_networks(self, id):
        return self.request_token('POST', '/api/v2/routers/networks', {'id': id})

    def rt_network_list(self, id):
        return self.request_token('POST', '/api/v2/routers/network_list', {'id': id})

    def rt_join_network(self, id, network_id, config):
        config['id'] = id
        config['network_id'] = network_id
        return self.request_token('POST', '/api/v2/routers/networks/join', config)

    def rt_rejoin_network(self, id, network_id, config):
        config['id'] = id
        config['network_id'] = network_id
        return self.request_token('POST', '/api/v2/routers/networks/rejoin', config)

    def rt_leave_network(self, id, network_id):
        config = {
            'id': id,
            'network_id': network_id,
        }
        return self.request_token('POST', '/api/v2/routers/networks/leave', config)

    def rt_apply_security_group(self, id, sgid, replace=False):
        replace_str = "0"
        if replace:
            replace_str = "1"
        data = self.request_token('POST', '/api/v2/routers/security_group/apply',
                                  {'id': id, 'security_group_id': sgid, 'replace': replace_str})
        return data

    def rt_leave_security_group(self, id, sgid):
        data = self.request_token('POST', '/api/v2/routers/security_group/leave',
                                  {'id': id, 'security_group_id': sgid})
        return data

    def rt_add_nat_role(self, id, config):
        config['id'] = id
        return self.request_token('POST', '/api/v2/routers/nats/add', config)

    def rt_update_nat_role(self, id, config):
        config['id'] = id
        return self.request_token('POST', '/api/v2/routers/nats/update', config)

    def rt_delete_nat_role(self, id, config):
        config['id'] = id
        return self.request_token('POST', '/api/v2/routers/nats/delete', config)

    # Database API
    def db_has_enough_resource(self, params):
        return self.request_token('POST', '/api/v2/databases/has_enough_resource', params)

    def db_provision(self, config):
        return self.request_token('POST', '/api/v2/databases/provision', config)

    def db_clone(self, id, config):
        config['id'] = id
        return self.request_token('POST', '/api/v2/databases/clone', config)

    def db_can_clone_with_network_ip(self, id, network_id, ip):
        params = {'id': id, 'network_id': network_id, 'ip_address': ip}
        return self.request_token('POST', '/api/v2/databases/can_clone_with_network_ip', params)

    def db_details(self, id):
        data = self.request_token('POST', '/api/v2/databases', {'id': id})
        return data

    def db_list(self, all_dbs=False, ids=None):
        params = {}
        if all_dbs:
            params['all'] = 'true'
        if ids:
            params['ids'] = ids
        data = self.request_token('POST', '/api/v2/databases', params)
        return data

    def db_jobs(self, id):
        data = self.request_token('POST', '/api/v2/databases/jobs', {'id': id})
        return data

    def db_show_job(self, jid):
        data = self.request_token('POST', '/api/v2/databases/job', {'id': jid})
        return data

    def db_start(self, id):
        data = self.request_token(
            'POST', '/api/v2/databases/start', {'id': id})
        return data

    def db_stop(self, id):
        data = self.request_token('POST', '/api/v2/databases/stop', {'id': id})
        return data

    def db_restart(self, id):
        data = self.request_token(
            'POST', '/api/v2/databases/restart', {'id': id})
        return data

    def db_resize(self, id, params):
        params['id'] = id
        data = self.request_token('POST', '/api/v2/databases/resize', params)
        return data

    def db_destroy(self, id):
        data = self.request_token(
            'POST', '/api/v2/databases/destroy', {'id': id})
        return data

    def db_set_tags(self, id, tags):
        data = self.request_token(
            'POST', '/api/v2/databases/set_tags', {'id': id, 'tags': tags})
        return data

    def db_binlogs(self, id):
        data = self.request_token(
            'POST', '/api/v2/databases/binlogs', {'id': id})
        return data

    def db_delete_binlogs(self, id, binlogs):
        data = self.request_token(
            'POST', '/api/v2/databases/binlogs/delete', {'id': id, 'binlogs': binlogs})
        return data

    def db_snapshots(self, id):
        data = self.request_token(
            'POST', '/api/v2/databases/snapshots', {'id': id})
        return data

    def db_create_snapshot(self, id):
        data = self.request_token(
            'POST', '/api/v2/databases/snapshots/create', {'id': id})
        return data

    def db_rollback_snapshot(self, id, name):
        data = self.request_token(
            'POST', '/api/v2/databases/snapshots/rollback', {'id': id, 'name': name})
        return data

    def db_delete_snapshot(self, id, name):
        data = self.request_token(
            'POST', '/api/v2/databases/snapshots/delete', {'id': id, 'name': name})
        return data

    def db_network_list(self, id):
        data = self.request_token(
            'POST', '/api/v2/databases/network_list', {'id': id})
        return data

    def db_networks(self, id):
        data = self.request_token(
            'POST', '/api/v2/databases/networks', {'id': id})
        return data

    def db_join_network(self, id, network_id, config):
        config['id'] = id
        config['network_id'] = network_id
        data = self.request_token(
            'POST', '/api/v2/databases/networks/join', config)
        return data

    def db_rejoin_network(self, id, network_id, config):
        config['id'] = id
        config['network_id'] = network_id
        data = self.request_token(
            'POST', '/api/v2/databases/networks/rejoin', config)
        return data

    def db_leave_network(self, id, network_id):
        config = {
            'id': id,
            'network_id': network_id,
        }
        data = self.request_token(
            'POST', '/api/v2/databases/networks/leave', config)
        return data

    def db_update_configuration(self, id, configurations, restart=True):
        restart_param = "1"
        if not restart:
            restart_param = "0"
        config = {
            'id': id,
            'configurations': configurations,
            'restart': restart_param,
        }
        data = self.request_token(
            'POST', '/api/v2/databases/configurations/update', config)
        return data

    def db_toggle_private_network(self, id):
        data = self.request_token(
            'POST', '/api/v2/databases/toggle_private_network', {'id': id})
        return data

    def db_download_server_ip(self, id):
        data = self.request_token(
            'POST', '/api/v2/databases/downloader', {'id': id})
        return data

    # datacenter API
    def dc_status(self, params):
        data = self.request_token('POST', '/api/v2/datacenter/status', params)
        return data

    # ssh key
    def create_ssh_public_key(self, public_key):
        return self.request_token('POST', '/api/v2/sshkey/create', {"public_key": public_key})

    def get_public_key_info(self, id):
        return self.request_token('POST', '/api/v2/sshkey/info', {"id": id})

    def delete_ssh_public_key(self, id):
        return self.request_token('POST', '/api/v2/sshkey/delete', {"id": id})

    def get_public_key_fingerprint(self, ids):
        return self.request_token('POST', '/api/v2/sshkey/fingerprint', {"ids": ids})

    def db_set_role(self, id, role):
        return self.request_token('POST', '/api/v2/databases/set_role', {"role": role, "id": id})

    # work order
    def handle_work_order(self):
        return self.request_token('POST', '/api/v2/work_order/handle')

    def work_order_info(self, work_order_id):
        return self.request_token('POST', '/api/v2/work_order/info', {'work_order_id': work_order_id})

    def completed_work_order(self):
        return self.request_token('POST', '/api/v2/work_order/completed')

    def work_order_cloud_server_params(self):
        return self.request_token('POST', '/api/v2/work_order/cloud_server/params')

    def create_work_order(self, params):
        return self.request_token('POST', '/api/v2/work_order/create', params)

    def work_order_physical_server_params(self):
        return self.request_token('POST', '/api/v2/work_order/physical_server/params')

    def work_order_database_params(self):
        return self.request_token('POST', '/api/v2/work_order/database/params')

    def work_order_volume_params(self):
        return self.request_token('POST', '/api/v2/work_order/volume/params')

    def work_order_default_products_and_flows(self, product_type):
        params = {
            'product_type': product_type
        }
        return self.request_token('POST', '/api/v2/work_order/product/flow/list', params)

    def delete_work_order(self, id):
        params = {
            'work_order_id': id
        }
        return self.request_token('POST', '/api/v2/work_order/delete', params)

    def withdraw_work_order(self, id):
        params = {
            'work_order_id': id
        }
        return self.request_token('POST', '/api/v2/work_order/withdraw', params)

    def show_pserver(self, id):
        data = self.request_token('POST', '/api/v2/physical_server/detail', {'id': id})
        return data
