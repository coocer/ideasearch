import { NavLink } from "react-router-dom";

const ITEMS = [
  { to: "/", label: "本期文章" },
  { to: "/generate", label: "生成新一期" },
  { to: "/topics", label: "研究方向" },
  { to: "/sources", label: "数据源" },
  { to: "/history", label: "历史文章" },
  { to: "/setup", label: "设置" },
];

export default function Rail() {
  return (
    <nav className="rail" aria-label="主导航">
      <div className="brand">
        研究雷达
        <small>ideasearch</small>
      </div>
      <ul className="navlist">
        {ITEMS.map((item) => (
          <li key={item.to}>
            <NavLink to={item.to} end={item.to === "/"}>
              {item.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
