// Environment-specific settings
const ENV = import.meta.env.MODE;

interface Settings {
    apiUrl: string;
    appName: string;
    logoUrl: string;
}

// Get the current host
const currentHost = window.location.hostname;
const isLocalhost = currentHost === 'localhost' || currentHost === '127.0.0.1';

const productionSettings: Settings = {
    apiUrl: 'https://api.cmr-bot.ai',
    appName: 'CMR Bot',
    logoUrl: '/cmr-logo.png'
};

const developmentSettings: Settings = {
    // Use the current host for the API URL in development
    apiUrl: isLocalhost ? 'http://localhost:8001' : `http://${currentHost}:8001`,
    appName: 'CMR Bot (Dev)',
    logoUrl: '/kh-logo.png'
};

// Select settings based on environment
const settings: Settings = ENV === 'production' ? productionSettings : developmentSettings;

export default settings;
