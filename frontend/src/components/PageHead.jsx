/** What this page is, in a title and one line. */
export default function PageHead({ title, children }) {
  return (
    <div className="head">
      <h1 className="head__title">{title}</h1>
      {children && <p className="head__subtitle">{children}</p>}
    </div>
  );
}
