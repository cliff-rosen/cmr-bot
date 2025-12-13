import PubMedSearch from '../components/tools/PubMedSearch';

export default function Tools() {
    return (
        <div className="max-w-6xl mx-auto p-6">
            <div className="mb-8">
                <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
                    Tools
                </h1>
                <p className="text-gray-600 dark:text-gray-400 mt-2">
                    Test and debug backend services
                </p>
            </div>

            <div className="space-y-8">
                <PubMedSearch />
            </div>
        </div>
    );
}
