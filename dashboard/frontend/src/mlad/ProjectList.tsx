import React, { useState } from 'react';
import { Project, ProjectSpec } from './models';

import { Drawer, Table } from 'antd'
import ProjectDetail from './ProjectDetail';

interface ProjectListProps {
	projects: Project[];
	projectSpec: ProjectSpec;
	setRequestData: Function;
}

export default function ProjectList({ projects, projectSpec, setRequestData }: ProjectListProps) {

	const [detailVisible, setDetailVisible] = useState(false);

	const onRow = (record: Project, rowIndex: number | undefined) => {
		return {
			onClick: () => {
				setRequestData({ key: record.key });
				setDetailVisible(true);
			}
		}
	}

	return (
		<>
			<Table
				dataSource={projects}
				columns={Project.getColumns()}
				rowKey="key"
				size='small'
				onRow={onRow}
			/>
			<Drawer
				title={`Project: ${projectSpec.key}`}
				visible={detailVisible}
				placement='right'
				width='736'
				closable={true}
				drawerStyle={{overflowY: 'scroll'}}
				onClose={() => setDetailVisible(false)}
			>
				<ProjectDetail projectSpec={projectSpec} />
			</Drawer>
		</>
	)
}
