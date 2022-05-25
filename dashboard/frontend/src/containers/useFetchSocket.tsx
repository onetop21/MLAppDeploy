import { useEffect, useState } from 'react';

export default function useFetchSocket<T>(url: string, schema: { new (args: any): T}) {
	const [data, setData] = useState<T[] | T>([]);
	const [connCounter, setConnCounter] = useState(0);
	const [requestData, setRequestData] = useState<any>({});

	useEffect(() => {

		const ws = new WebSocket(url);
		let connected = false;
		ws.onopen = () => {
			connected = true;
			ws.send(JSON.stringify(requestData));
		};

		ws.onmessage = ({ data }: MessageEvent) => {
			const raw = JSON.parse(data);
			const code = raw['status_code'];
			if (code === 200) {
				// 데이터가 array인 경우 schema로 지정된 객체를 array로 생성
				if (Array.isArray(raw['data'])) {
					setData((raw['data'] as any[]).map((d: any) => new schema(d)));
				} else {
					setData(new schema(raw['data']));
				}
			} else {
				console.log(raw['message']);
			}
		};

		ws.onclose = () => { connected = false; }
		ws.onerror = () => { connected = false; }
		
		// 연결이 끊키면 5초 마다 다시 connection을 요청함
		const reconnectionInterval = setInterval(() => {
			if (!connected) {
				setConnCounter(c => c + 1);
			}
		}, 5000);

		const messageInterval = setInterval(() => {
			if (connected) {
				// 대부분 빈 객체를 requestData로 보내지만 project detail인 경우에는
				// project key를 담아서 보낸다. 
				ws.send(JSON.stringify(requestData));
			}
		}, 1000);
		return () => {
			clearInterval(reconnectionInterval);
			clearInterval(messageInterval);
			ws.close();
		};
	}, [url, schema, requestData, connCounter]);

	return {
		data, setRequestData
	};
}
