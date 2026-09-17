/** What this page is, in a title and one line, with any action beside it. */
export default function PageHead({ title, action, children }) {
  return (
    <div className="head">
      <div className="head__row">
        <h1 className="head__title">{title}</h1>
        {action}
      </div>
      {children && <p className="head__subtitle">{children}</p>}
    </div>
  );
}
