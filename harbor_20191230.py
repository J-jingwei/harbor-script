#!/usr/bin/env python3
# --coding:utf-8--
'''本脚本适用于清理释放harbor镜像仓库空间；
    此脚本基于harbor 1.9.0版本编写；
    harbor 1.7.0 以后版本可通过页面垃圾回收；
    如不同版本api不同需自行更改各个函数中url部分。'''

import json
import heapq
import requests
from requests.auth import HTTPBasicAuth
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from tqdm import tqdm
from time import sleep, time
import traceback


class Harbor(object):
    def __init__(self, api_url, user, num, exclude):
        """
        初始化一些基本参数
        :param auth: login password authority management
        :param head: change user-agent
        :param url: harbor server api url
        :param project_exclude: Exclude project team
        :param num_limit: Limit the number of retained versions
        :param project_special: project dict id and repo total
        :param project_state: project dict name and id
        :param repo_state: repo dict name and tag total
        :param repo_dispose: Count the number of tag processing
        :param tag_state: tag dict repo_name and tag
        """
        self.auth = user
        self.head = {"user_agent": "Mozilla/5.0"}
        self.url = api_url
        self.project_exclude = exclude
        self.num_limit = int(num)
        self.project_special = {}
        self.project_state = {}
        self.repo_state = {}
        self.repo_dispose_count = 0
        self.tag_state = {}

    def setting(self):
        self.session = requests.Session()
        self.session.auth = self.auth
        retry = Retry(connect=3, backoff_factor=1)
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount('https://', adapter)
        self.session.keep_alive = False

    def list_project(self):
        try:
            r_project = self.session.get("{}/projects".format(self.url), headers=self.head)
            r_project.raise_for_status()
            # 将得到的文本转换格式
            project_data = json.loads(r_project.text)
            for i in project_data:
                # 项目组名称
                project_name = i.get('name')
                # 项目组id
                project_id = i.get('project_id')
                # 项目组仓库
                project_repo = i.get('repo_count')
                # 利用一个字典将项目名称与id对应起来
                self.project_state[project_name] = project_id
                # 由于请求限制，另外用一个字典,对应id于repo总数
                self.project_special[project_id] = project_repo
                print("\033[0;32m项目名称:{}\t项目编号:{}\t项目下仓库统计:{}\033[0m".format(project_name, project_id, project_repo))
            print("\033[0;36mproject:项目组对应id列表:{}\033[0m".format(self.project_state))
            print("\033[0;36mproject:项目id对应仓库数:{}\033[0m".format(self.project_special))
        except:
            traceback.print_exc()
            raise

    def list_repo(self):
        try:
            for a in self.project_state.keys():
                # 排除部分项目组
                if a not in self.project_exclude:
                    id = self.project_state.get(a)
                    # print(id)
                    # 由于请求限制，得出需请求的次数，整除+1
                    number = self.project_special.get(id) // 100 + 1
                    for i in range(number):
                        page = i + 1
                        r_repo = self.session.get(
                            "{}/repositories?project_id={}&page={}&page_size=100".format(self.url, id, page),
                            headers=self.head)
                        # 将得到的文本结果转换格式
                        repo_data = json.loads(r_repo.text)
                        for r in repo_data:
                            repo_id = r.get('id')
                            repo_name = r.get('name')
                            tag_count = r.get('tags_count')
                            # 利用字典将仓库名称与tag总量对应起来
                            self.repo_state[repo_name] = tag_count
            print("\033[0;31mrepo:排除部分项目组后，需过滤处理的仓库总量为:{}\033[0m".format(len(self.repo_state)))

        except:
            traceback.print_exc()
            raise

    def list_tag(self):
        try:
            # n 为repo 仓库名字
            for n in self.repo_state.keys():
                # 如果该仓库下版本总数大于数量限制，继续往下走
                if self.repo_state.get(n) > self.num_limit:
                    r_tag = self.session.get('{}/repositories/{}/tags'.format(self.url, n))
                    # print(r_tag.status_code)
                    # if r_tag.status_code != 200:
                    #     print(n)
                    #     continue
                    tag_data = json.loads(r_tag.text)
                    tag_dict = {}
                    for t in tag_data:
                        # 取出各个tag的名字
                        tag_name = t.get('name')
                        # 切分各个tag，取出日期时间部分
                        tag_time = int(tag_name.split('.')[-1])
                        # 将tag名称与切割出来的时间部分对应起来
                        tag_dict[tag_time] = tag_name
                    tagtime_list = []
                    tagname_list = []
                    for h in tag_dict.keys():
                        tagtime_list.append(h)
                    # 取出时间最大值三个
                    max_limit = heapq.nlargest(3, tagtime_list)
                    # 取反，将key不为这三个的value版本号找出来
                    for q in tag_dict.keys():
                        if q not in max_limit:
                            name = tag_dict.get(q)
                            tagname_list.append(name)
                    self.tag_state[n] = tagname_list
                    self.repo_dispose_count += len(tagname_list)
            print("\033[0;31mtag:本次过滤出需处理涉及仓库共:{}个，涉及删除镜像版本共:{}个\033[0m".format(len(self.tag_state),
                                                                                self.repo_dispose_count))
        except:
            traceback.print_exc()
            raise

    def del_tag(self):
        try:
            delete_total = 0
            del_faild = []
            if self.repo_dispose_count == 0:
                print("\033[0;34mdel:本次无需删除tag\033[0m")
            else:
                print("\033[0;34mdel:删除tag阶段耗时较长:请耐心等待\033[0m")
                pbar1 = tqdm(total=self.repo_dispose_count, unit='个', unit_scale=True)
                # na 为repo 名称
                for na in self.tag_state:
                    # ta为需删除的tag版本号
                    for ta in self.tag_state[na]:
                        try:
                            r_del = self.session.delete('{}/repositories/{}/tags/{}'.format(self.url, na, ta),
                                                    headers=self.head,
                                                    auth=self.auth)
                            r_del.raise_for_status()
                            delete_total += 1
                            pbar1.update(1)
                        except:
                            print('del: {}仓库下删除版本号:{}失败！！！'.format(na, ta))
                            del_faild.append(na + ':' + ta)
                sleep(3)
                pbar1.close()
                print("\033[0;34mdel:需删除镜像已完成删除！ 共删除版本数量:{}个\033[0m".format(delete_total))
                print('删除失败共计：{}，删除失败的为：{}'.format(len(del_faild), del_faild))
        except:
            traceback.print_exc()
            raise

    def volume_recycle(self):
        try:
            if self.repo_dispose_count == 0:
                print("\033[0;35mvolume:本次无需清理存储\033[0m")
            else:
                # 定义一个立即执行垃圾清理的json
                da = {"schedule": {"cron": "Manual", "type": "Manual"}}
                print("\033[0;35mvolume:开始回收存储空间！\033[0m")
                r_volume = self.session.post('{}/system/gc/schedule'.format(self.url), json=da)
                r_volume.raise_for_status()
                print("\033[0;35mvolue:回收存储空间已完成！\033[0m")
        except:
            traceback.print_exc()
            raise


def main(api_url, login, num, exclude):
    start = time()
    try:
        # begin开始
        har = Harbor(api_url=api_url, user=login, num=num, exclude=exclude)
        # 配置
        har.setting()
        # 列出项目组
        har.list_project()
        # 列出repo仓库
        har.list_repo()
        # 列出tag版本
        har.list_tag()
        # 删除不保留版本
        # har.del_tag()
        # 回收存储
        # har.volume_recycle()
        print("所有操作运行完成！")
        end = time()
        allTime = end - start
        print("运行结束共耗时:{:.2f}s".format(allTime))
    except:
        end = time()
        allTime = end - start
        # traceback.print_exc()
        print('清理出错！')
        print("运行结束共耗时:{:.2f}s".format(allTime))


if __name__ == '__main__':
    # harbor api interface
    api_url = "https://images.lingcb.net/api"
    # Login ,change username and password
    login = HTTPBasicAuth('admin', '120110')
    # 需要排除的项目组，自行根据情况更改，或为空
    exclude = ['k8s', 'basic', 'library']
    # 仓库下版本过多，需保留的最近版本数量
    keep_num = 3
    # 启动Start the engine
    main(api_url=api_url, login=login, num=keep_num, exclude=exclude)
