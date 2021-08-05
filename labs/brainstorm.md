# 고민거리
## MLAD의 목표는 무엇인가.
* 학습 시스템을 쉽게 구축하고, 데이터 프로세싱/학습/배포를 쉽게 하도록 도와주는 녀석
* 프로젝트 당 한 클러스터를 구축하고 쉽게 리소스를 공유하는데 초점
* 개인적으로 쉽게 구축가능하면서, 일부 여럿이 썼을 때도 잘 동작하도록?
  * 주: 개인 / 부: 그룹 (관리자 필요)
## 인증 방식은 어떻게 할 것인가?
* 별도의 인증은 없다. 다만, 간단한 방식을 통해 user/hostname을 통해 구분 필요.
  * As-Is: User: $User
  * To-Be: User: $...
## 개인/관리자 어떻게 R&R을 나눌 것인가?
* 별도 R&R은 없고 관리 권한이 있는 클라이언트에서 관리 기능 사용 가능
* 관리 기능
  * 노드 레이블 추가/삭제
  * 프로젝트 강제 내림
  * 프로젝트 리소스 강제제한
  * (진짜 최소한의 인증 허가?)
  * 플러그인 설치? (좀 더 고민해보고)
    * JupyterHub
    * PromStack
## Admin/User간 구분 및 사용이 더 단순해질 순 없을까?
* kubeconfig 있는 시스템은 admin권한 있음
## Admin은 CLI에서 관리? APIServer에서 관리?
* Admin 명령은 CLI에서 관리하는게 맞을 것 같음
## User는 CLI에서 관리? APIServer에서 관리?
* User는 API Server를 통해 동작 
* API Server는 Admin관련 동작 관리 필요 없음 (Authorize 필요 없어짐)
  * API Server의 용도는?
    * 프로젝트 생성
    * 프로젝트 내 서비스 실행
    * CLI로 프로젝트 
## Dashboard는 어디서 띄울 것인가?
* 무엇을 띄울 것인가?
  * 공용 컴포넌트
    * 시스템 리소스 현황
    * 프로젝트 현황
  * 개인별 컴포넌트
    * JupyterLab from JupyterHub(Plugin?)
    * VSCode
    * SSH Workspace
    * Tensorboard
    * Piperbaord
    * Hyppobaord
    * ...
개인화된 대시보드는 로컬에서 띄우는게 맞는 것이라고 봄
## YAML Legacy 버릴 것인가?
* 버려야지
## CLI 명령어/YAML의 항목분류를 명확하게 정의할 수 없을까?
* 용어
  * 학습 - 프로젝트
  * 배포 - 서비스
* build
  * 프로젝트만 빌드 하고 싶음 (플러그인 빼고)
  * 서비스는? -> 프로젝트는 학습과 배포 모두 포함?
  * docker build
* up/down
  * docker push -> docker run
  * 프로젝트(학습, 배포) 실행 (Bg로)
  * Foreground로 띄울 순 없을까? 그럴일이 있을까?
* run <python file> (후보)
  * mlad run piper_entry.py --arguments ... 
    * build -> up -> log -> down
  * docker run -it --rm
* deploy (보류)
  * kubectl deployment controller 사용
* dashboard or component
  * Local Docker에 Dashboard Daemon 실행
  * component 관리
* logs
* node
* ps
* ls
  * --me 있으면 좋을듯
* top (조금 더 고민해봅시다.)
  * node: top node -> node에 통합
  * project: top (외부에서 혹은 -a)
  * service: top (내부에서)
* context (보류) 
  * admin만 가능 
  * 개발용, 배포용 선택?
* config or export ? (고민만 해보고 있음)
  * 현재 mlad-project.yaml -> kube Workload로 바꿔주는 용도
## 분산 처리를 NCML에서 지원이 가능할까?
  * Result <- Job <-> Job <-> Job (MapReduce) 
  * 고민 해보면 좋을 듯.
## 서비스가 계속 떠있는 형태가 좋을까? 아니면 실행할 때 띄워주는 형태가 좋을까?
* kubernetes API를 이용한 MLAD SDK를 개발하고 이를 이용하여 데몬을 직접 띄우는 식으로 하면 어떨지...
  * Kubectl로만 동작하게 하면 서비스 없이도 동작하게 가능.
  * MLAD가 상당히 독립적인 서비스로도 사용이 가능할듯. (설치없이도 사용 가능)
  * 고민해봅시다...
## Repo name 변경 및 버전 관리
* refactoring -> master
* 기본 docker version은 version tag해서 끝내고
* 0.1.0 부터 시작?
* 그리고 master는 배포용, 개발은 dev branch / hotfix branch 사용 후 pr/merge
## Sub Job/Service의 Resource 관리는?
* 준회님에게 고민을 맞기겠음.
* 효일 의견) 프로젝트 단위로 한 번 더 Resource Quota 설정
* 또한, SubProject에서 직접 Resource를 할당할 것인가, 정의된 Preset으로 가져갈것인가, ~~부모의 res를 계승할 것인가.~~
## Project 파일에 손자 서비스/잡이 안보이는게 당연한 것일까? (보류)
* 이것도 고민 거리?

## CLI / API Server / SDK 별 동작 Role
* CLI
  * Project List
  * Node List
  * 
  * API Server 연동
* API Server
  * Project(Namespace) 생성 및 Role 설정
  * Project에 Entry App 추가
  * Project내 App List, Status, Log 취합
* SDK
  * Project내 App 생성, 삭제
  * Project내 App List, Status, Log 취합


# 역할 나누기
* 일감
  * Admin API를 CLI로 옮기기 (도연님)
  * Admin Authorize를 Kubeconfig로 판단하기 (도연님)
  * replication controller -> deployment로 교체 (도연님)
  * build (mlad image build) (도연님)
    * build -> local image만 만들기?
    * project/deploy/dashboard에서 up,install 시 retag해서 적용하기
  * Plugin Command -> dashboard? component로 옮기기 (준회님)
    * mlad dashboard
      * mlad dashboard up
      * mlad dashboard down
      * mlad dashboard install [COMPONENT]
      * mlad dashboard uninstall [COMPONENT]
      * mlad dashbaord ls
      * mlad dashboard ps
  * project (도연님)
    * run 개발
      * YAML의 app사용 안할 때
        mlad run -- python app.py --test-args 1 -- test-arg-name Hello
    * ls
      * 기본적으로 클러스터 내 모든 잡 보여주기
      * ls를 통해 내 프로젝트를 보여주기?
        * --all? --own
    * top
      * node -> node에 node top 생성
      * project -> ls ps에 통합
  * deploy(command, admin 전용)  (도연님)
    * Ingress 주소
    * up: rolling update
    * down: kill
    * undo: revert
    * history: ?
    * config ?? - 나중에 생각하기로.
  * context (준회님)
    mlad --context/-c 지원 ? 이건 오케
    * use
    * add
    * del
    * ls
    * set
  * auto completion (준회님)
    * 유지보수
