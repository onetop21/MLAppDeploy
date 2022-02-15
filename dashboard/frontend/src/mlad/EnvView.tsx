import React from 'react';

interface EnvViewProps {
	env: {name: string, value: string}[];
};

export default function EnvView({ env }: EnvViewProps) {
	return <div>
		{env.map(e => {
			return <div style={{lineHeight: '2'}} key={e.name}>
				<span style={{color: '#777'}}>{e.name}: </span>
				<span>{e.value}</span>
			</div>
		})}
	</div>
}
