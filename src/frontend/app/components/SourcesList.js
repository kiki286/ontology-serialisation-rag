import SourceItem from "./SourceItem";


export default function SourcesList({ sources }) {
    return (
        <ul className="mt-2 list-none text-gray-800 dark:text-gray-200 p-2 rounded-md">
            {sources.map((src, i) => (
                <SourceItem key={i} src={src} />
            ))}
        </ul>
    );
}