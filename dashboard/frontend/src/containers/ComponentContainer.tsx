import React from 'react';


interface ComponentContainerProps {
	host: string;
}


export default function ComponentContainer({ host }: ComponentContainerProps) {
	return <div>
		<iframe
			src={host} title={host}
			allowFullScreen width="100%"
			style={{display: 'block', height: '100vh'}}
		/>
	</div>
}
