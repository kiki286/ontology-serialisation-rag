export default function ResponseCard({ response }) {
  if (!response) return null;
  return (
    <div className="mt-4 p-4 bg-gray-100 dark:bg-gray-800 rounded-md">
      <strong className="block mb-1 text-gray-700 dark:text-gray-300">
        Response:
      </strong>
      <p className="text-gray-900 dark:text-gray-100 whitespace-pre-line">
        {response}
      </p>
    </div>
  );
}
