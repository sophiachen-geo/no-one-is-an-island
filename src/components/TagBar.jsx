export default function TagBar({ allTags, activeTag, onTagClick }) {
  return (
    <div className="tag-bar">
      <button
        className={`tag-pill${!activeTag ? ' active' : ''}`}
        onClick={() => onTagClick(null)}
      >
        all
      </button>
      {allTags.map(tag => (
        <button
          key={tag}
          className={`tag-pill${activeTag === tag ? ' active' : ''}`}
          onClick={() => onTagClick(activeTag === tag ? null : tag)}
        >
          {tag}
        </button>
      ))}
    </div>
  );
}
