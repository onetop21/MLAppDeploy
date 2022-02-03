import React from 'react';
import { Metric } from './models';

import { Table, Typography } from 'antd';
import styles from './mlad.module.css';

const { Title } = Typography;

interface ExpandedRowProps {
	labels: string[];
	metrics: Metric[];
};

export default function ExpandedRow({ labels, metrics }: ExpandedRowProps) {
	return (
		<div className={styles.expandedRow}>
			<div>
				<Title level={5}>Labels</Title>
				<ul>
					{labels.map(label => <li key={label}>{label}</li>)}
				</ul>
			</div>
			<div>
				<Title level={5}>Metrics</Title>
				<Table
					dataSource={metrics}
					rowKey='type'
					columns={Metric.getColumns()}
					pagination={false} />
			</div>
		</div>
	);
};
