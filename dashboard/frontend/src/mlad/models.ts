import internal from "stream";

export class Metric {
	type: string;
	capacity: number;
	used: number | string;
	free: number;

	static MSG_COLLECTING = 'Collecting...';

	constructor(raw: any) {
		this.type = this.parseType(raw['type']);
		this.capacity = raw['capacity'];
		this.used = raw['used'] === null ? Metric.MSG_COLLECTING : raw['used'];
		this.free = raw['free'];
	}

	static getColumns() {
		return [
			{ title: 'TYPE', dataIndex: 'type', key: 'type' },
			{ title: 'CAPACITY', dataIndex: 'capacityText', key: 'capacityText' },
			{ title: 'USED', dataIndex: 'usedText', key: 'usedText' },
			{ title: 'FREE (%)', dataIndex: 'freeText', key: 'freeText' },
		]
	}

	parseType(type: string) {
		switch (type) {
			case 'mem':
				return 'Memory (Mi)';
			case 'cpu':
				return 'CPU (Cores)';
			case 'gpu':
				return 'GPU (#)';
			default:
				return '-'
		}
	}

	get freeText() {
		if (this.used === Metric.MSG_COLLECTING) {
			return Metric.MSG_COLLECTING;
		} else {
			const percent = ((1 - (this.used as number) / this.capacity) * 100).toFixed(1);
			return `${percent}%`;
		}
	}

	get capacityText() {
		return this.capacity.toFixed(0);
	}

	get usedText() {
		return this.used === Metric.MSG_COLLECTING
			? this.used
			: (this.used as number).toFixed(2);
	}
}

export class Node {
	id: string;
	hostname: string;
	role: string;
	state: string;
	availability: string;
	engine: string;
	labels: string[];
	metrics: Metric[];

	constructor(raw: any)	{
		this.id = raw['id'];
		this.hostname = raw['hostname'];
		this.role = raw['role'];
		this.state = raw['status']['State'];
		this.availability = raw['availability'];
		this.engine = raw['engine_version'];
		this.labels = Object.entries(raw['labels'])
			.map(([key, value]) => `${key}=${value}`);
		this.metrics = (raw['metrics'] as any[])
			.map(m => new Metric(m))
			.sort((a, b) => a.type.localeCompare(b.type));
	}

	static getColumns() {
		return [
			{ title: 'ID', dataIndex: 'id', key: 'id' },
			{ title: 'HOSTNAME', dataIndex: 'hostname', key: 'hostname' },
			{ title: 'ROLE', dataIndex: 'role', key: 'role' },
			{ title: 'STATE', dataIndex: 'state', key: 'state' },
			{ title: 'AVAILABILITY', dataIndex: 'availability', key: 'availability' },
			{ title: 'ENGINE', dataIndex: 'engine', key: 'engine' },
		]
	}
}

export class Project {
	key: string;
	userName: string;
	name: string;
	image: string;
	numApps: number;
	numReplicas: number;
	numTasks: number;
	hostname: string;
	workspace: string;
	cpu: number;
	gpu: number;
	mem: number;

	constructor(raw: any) {
		this.key = raw['key'];
		this.userName = raw['username'];
		this.name = raw['name'];
		this.image = raw['image'];
		this.numApps = raw['n_apps'];
		this.numReplicas = raw['n_replicas'];
		this.numTasks = raw['n_tasks'];
		this.hostname = raw['hostname'];
		this.workspace = raw['workspace'];
		this.cpu = (raw['cpu'] || 0).toFixed(2);
		this.gpu = (raw['gpu'] || 0).toFixed(2);
		this.mem = (raw['mem'] || 0).toFixed(2);
	}

	static getColumns() {
		return [
			{ title: 'KEY', dataIndex: 'key', key: 'key' },
			{ title: 'USERNAME', dataIndex: 'userName', key: 'userName' },
			{ title: 'NAME', dataIndex: 'name', key: 'name' },
			{ title: 'IMAGE', dataIndex: 'image', key: 'image' },
			{ title: 'APPS', dataIndex: 'numApps', key: 'numApps'},
			{ title: 'TASKS', dataIndex: 'numTasks', key: 'numTasks',
			  render: (numTasks: number, project: Project) => `${numTasks}/${project.numReplicas}`
			},
			{ title: 'CPU', dataIndex: 'cpu', key: 'cpu'},
			{ title: 'GPU', dataIndex: 'gpu', key: 'gpu'},
			{ title: 'MEMORY (MB)', dataIndex: 'mem', key: 'mem'},
		]
	}
}

export class TaskSpec {
	name: string;
	nodeName: string;
	phase: string;
	cpu: string;
	gpu: string;
	mem: string;

	constructor(raw: any, resources: any) {
		this.name = raw['name'];
		this.nodeName = raw['node'];
		this.phase = raw['phase'];
		this.cpu = this.parseResource(resources[this.name], 'cpu');
		this.gpu = this.parseResource(resources[this.name], 'gpu', 0);
		this.mem = this.parseResource(resources[this.name], 'mem');
	}

	get running() {
		return this.phase === 'Running';
	}

	parseResource(resource: any, key: string, precision: number = 2) {
        return typeof resource[key] === 'string'
            ? resource[key]
            : resource[key].toFixed(precision);
	}
}

export class Expose {
    port: number;
    ingress?: { path: string }

    constructor(raw: any) {
        this.port = raw['port'];
        this.ingress = raw['ingress'];
    }
}

export class AppSpec {
	name: string;
	cpu: string;
	gpu: string;
	mem: string;
	env: {name: string, value: string}[];
    exposes: Expose[];
	taskSpecs: TaskSpec[];

	constructor(raw: any) {
		this.name = raw['name'];
		this.cpu = this.parseResource(raw['resources'], 'cpu');
		this.gpu = this.parseResource(raw['resources'], 'gpu', 0);
		this.mem = this.parseResource(raw['resources'], 'mem');
		this.env = raw['env'] || [];
        this.exposes = (raw['expose'] as any[]).map(d => new Expose(d)); 
		this.taskSpecs = Object.values(raw['task_dict'] as any[]).map(d => new TaskSpec(d, raw['resources']));
	}

	get statusColor(): string {
		const numRunningTasks = this.taskSpecs
			.reduce((acc, curr) => acc + (curr.running ? 1 : 0), 0)
		if (numRunningTasks === this.taskSpecs.length) {
			return 'green';
		} else if (numRunningTasks > 0) {
			return 'orange';
		} else {
			return 'red';
		}
	}

	get status(): string {
		const numRunningTasks = this.taskSpecs
			.reduce((acc, curr) => acc + (curr.running ? 1 : 0), 0);
		return `${numRunningTasks}/${this.taskSpecs.length}`;
	}

	parseResource(raw: any, key: string, precision: number = 2) {
		return Object.values(raw)
			.reduce<number>((acc, curr: any) => {
                let value = curr[key];
                if (typeof value === 'string') {
                    value = 0;
                }
                return value + acc;
            }, 0)
			.toFixed(precision);
	}
}

export class ProjectSpec {
	key: string;
	age: string;
	name: string;
	userName: string;
	image: string;
	namespace: string;
	version: string;
	hostname: string;
	projectPath: string;
	cpu: string;
	gpu: string;
	mem: string;
	yaml: any;
	appSpecs: AppSpec[];

	constructor(raw: any) {
		this.key = raw['key'];
		this.age = this.obtainTimeDelta(raw['created']);
		this.name = raw['project'];
		this.userName = raw['username'];
		this.image = raw['image'];
		this.namespace = raw['name'];
		this.version = raw['version'];
		this.hostname = (raw['workspace'] || { hostname: '-' })['hostname'];
		this.projectPath = (raw['workspace'] || { path: '-' })['path'];
		this.cpu = (raw['cpu'] || 0).toFixed(2);
		this.gpu = (raw['gpu'] || 0).toFixed(2);
		this.mem = (raw['mem'] || 0).toFixed(2);
		this.yaml = JSON.parse(raw['project_yaml'] || '{}');
		this.appSpecs = ((raw['apps'] || []) as any[]).map(d => new AppSpec(d));
	}

	obtainTimeDelta(created: string): string {
		const createdDate = new Date(created);
		const suffix = `(Created: ${createdDate.toLocaleString()})`;
		const delta = Math.floor(((new Date()).getTime() - createdDate.getTime()) / 1000);
		if (delta < 120) {
			return `${delta}s ${suffix}`;
		} else if (delta < 3600) {
			return `${Math.floor(delta / 60)}m${delta % 60}s ${suffix}`;
		} else if (delta < 3600 * 24) {
			const hours = Math.floor(delta / 3600);
			const mins = Math.floor((delta - hours * 3600) / 60);
			return `${hours}h${mins}m ${suffix}`;
		} else {
			const days = Math.floor(delta / 3600 / 24);
			const hours = Math.floor((delta - days * 3600 * 24) / 3600);
			return `${days}d${hours}h ${suffix}`;
		}
	}
}
