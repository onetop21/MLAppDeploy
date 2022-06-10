import React, { useEffect } from 'react';
import { Node } from './models';

import { Table } from 'antd';
import ExpandedRow from './ExpandedRow';


interface NodeListProps {
	nodes: Node[];
}
/**
 * Nodes Tab에서 보여줄 view 
 */
export default function NodeList({ nodes }: NodeListProps) {

	useEffect(() => {
	}, [nodes]);

	return (
		<Table
			dataSource={nodes}
			columns={Node.getColumns()}
			rowKey="id"
			expandable={{
				expandedRowRender: record => <ExpandedRow {...record} />
			}}
		/>
	)
};
