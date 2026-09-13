import React from 'react';

interface Props {
  onSelectDept?: (dept: string) => void;
}

export const DepartmentsScreen: React.FC<Props> = ({ onSelectDept }) => {
  const depts = [
    { num: '01 //', name: 'Tech', count: '4 AGENTS', active: true },
    { num: '02 //', name: 'Operations', count: '2 AGENTS', active: false },
    { num: '03 //', name: 'Strategy', count: '1 AGENT', active: false },
  ];

  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] min-h-[75vh]">
      <div className="border-b border-[#0A0A0A] pb-3">
        <span className="font-mono text-[10px] text-zinc-500 tracking-widest uppercase">
          STRUCTURE
        </span>
        <h2 className="text-3xl font-headline font-bold mt-1 text-[#0A0A0A]">
          Departments
        </h2>
      </div>

      <div className="flex-1 flex flex-col divide-y divide-[#0A0A0A] my-4">
        {depts.map((d) => (
          <div
            key={d.name}
            onClick={() => onSelectDept?.(d.name)}
            className="py-6 flex items-center justify-between hover:bg-black hover:text-white transition-colors cursor-pointer group px-2"
          >
            <div>
              <span
                className={`font-mono text-xs font-bold ${
                  d.active ? 'text-[#E6391E]' : 'text-zinc-400 group-hover:text-zinc-300'
                }`}
              >
                {d.num}
              </span>
              <span className="text-xl font-medium ml-2">{d.name}</span>
            </div>
            <span className="font-mono text-xs text-zinc-500 group-hover:text-zinc-300">
              {d.count}
            </span>
          </div>
        ))}
      </div>

      <div>
        <button className="w-full bg-[#0A0A0A] text-white py-4 font-headline text-base uppercase tracking-wider hover:bg-[#E6391E] transition-colors border border-[#0A0A0A]">
          Add Department +
        </button>
      </div>
    </div>
  );
};
