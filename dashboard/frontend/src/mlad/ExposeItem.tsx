import React from 'react';
import { Expose } from './models';
import ProjectDetailListItem from './ProjectDetailListItem';


interface ExposeItemProps {
  exposes: Expose[];
}
/**
 * TaskView에서 expose 정보를 나타내기 위한 view
 */
export default function ExposeItem({ exposes }: ExposeItemProps) {
  return <>
    <ProjectDetailListItem name='Expose' value='' />
    <div style={{paddingLeft: '30px'}}>
      {exposes.map(expose => {
        return <div key={expose.port}>
          <ProjectDetailListItem name='Port' value={expose.port.toString()} />
          {expose.ingress
            ? <ProjectDetailListItem name='Ingress Path' value={expose.ingress?.path} />
            : <></>}
        </div>
      })}
    </div>
  </>
}
