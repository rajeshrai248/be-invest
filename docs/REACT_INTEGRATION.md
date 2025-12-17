# React Frontend Integration Guide

> Complete guide for integrating BE-Invest API into React applications with examples for all available functionalities.

## Table of Contents

- [Quick Setup](#quick-setup)
- [API Client Setup](#api-client-setup)
- [Core Components](#core-components)
- [Broker Management](#broker-management)
- [Fee Comparison](#fee-comparison)
- [Investment Scenarios](#investment-scenarios)
- [Real-time Features](#real-time-features)
- [State Management](#state-management)
- [Error Handling](#error-handling)
- [Performance Optimization](#performance-optimization)
- [TypeScript Support](#typescript-support)

## Quick Setup

### Prerequisites

```bash
# Create new React app
npx create-react-app be-invest-client
cd be-invest-client

# Install required dependencies
npm install axios react-query @tanstack/react-query
npm install recharts  # For charts
npm install @headlessui/react @heroicons/react  # For UI components

# Optional: TypeScript support
npm install --save-dev @types/react @types/node typescript
```

### Environment Configuration

Create `.env.local`:

```env
# API Configuration
REACT_APP_API_BASE_URL=http://localhost:8000
# For production: https://your-domain.vercel.app

# Optional: Enable development features
REACT_APP_ENABLE_DEBUG=true
REACT_APP_ENABLE_MOCK_DATA=false
```

## API Client Setup

Create `src/services/api.js`:

```javascript
// API Client with error handling and request/response interceptors
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

// Create axios instance with default config
const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for debugging
apiClient.interceptors.request.use(
  (config) => {
    if (process.env.REACT_APP_ENABLE_DEBUG === 'true') {
      console.log('API Request:', config.method?.toUpperCase(), config.url, config.data);
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => {
    if (process.env.REACT_APP_ENABLE_DEBUG === 'true') {
      console.log('API Response:', response.status, response.data);
    }
    return response;
  },
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    
    // Handle specific error types
    if (error.response?.status === 429) {
      throw new Error('Rate limit exceeded. Please try again later.');
    }
    
    if (error.response?.status >= 500) {
      throw new Error('Server error. Please try again later.');
    }
    
    throw new Error(error.response?.data?.error?.message || 'An error occurred');
  }
);

export default apiClient;
```

Create `src/services/brokerApi.js`:

```javascript
// Broker API service with all available endpoints
import apiClient from './api';

export const brokerApi = {
  // Core broker operations
  async getAllBrokers() {
    const response = await apiClient.get('/brokers');
    return response.data;
  },

  async getBrokerFees(brokerName, filters = {}) {
    const params = new URLSearchParams();
    if (filters.instrumentType) params.append('instrument_type', filters.instrumentType);
    if (filters.orderChannel) params.append('order_channel', filters.orderChannel);
    
    const response = await apiClient.get(`/brokers/${brokerName}/fees?${params}`);
    return response.data;
  },

  // Fee comparison
  async compareBrokers(comparisonData) {
    const response = await apiClient.post('/compare', comparisonData);
    return response.data;
  },

  // Find cheapest broker
  async findCheapestBroker(amount, instrumentType, includeCustodyFees = false) {
    const params = new URLSearchParams({
      instrument_type: instrumentType,
      include_custody_fees: includeCustodyFees.toString(),
    });
    
    const response = await apiClient.get(`/cheapest/${amount}?${params}`);
    return response.data;
  },

  // Investment scenarios
  async analyzeScenarios(scenarioData) {
    const response = await apiClient.post('/scenarios', scenarioData);
    return response.data;
  },

  // LLM extraction (if available)
  async triggerExtraction(extractionData) {
    const response = await apiClient.post('/extract', extractionData);
    return response.data;
  },

  async getExtractionStatus(extractionId) {
    const response = await apiClient.get(`/extract/${extractionId}`);
    return response.data;
  },

  // Data validation
  async validateData(validationData) {
    const response = await apiClient.post('/validate', validationData);
    return response.data;
  },

  // Reports
  async generateReport(reportData) {
    const response = await apiClient.post('/reports/generate', reportData);
    return response.data;
  },

  async downloadReport(reportId, format = 'json') {
    const response = await apiClient.get(`/reports/${reportId}/download?format=${format}`, {
      responseType: format === 'pdf' ? 'blob' : 'json'
    });
    return response.data;
  },

  // Health check
  async getHealth() {
    const response = await apiClient.get('/health');
    return response.data;
  },

  // News endpoints
  async scrapeNews(brokers = [], force = false) {
    const params = new URLSearchParams();
    if (brokers.length > 0) {
      brokers.forEach(broker => params.append('brokers_to_scrape', broker));
    }
    if (force) params.append('force', 'true');
    
    const response = await apiClient.post(`/news/scrape?${params}`);
    return response.data;
  },

  async getAllNews() {
    const response = await apiClient.get('/news');
    return response.data;
  },

  async getBrokerNews(brokerName) {
    const response = await apiClient.get(`/news/broker/${brokerName}`);
    return response.data;
  },

  async getRecentNews(limit = 10) {
    const response = await apiClient.get(`/news/recent?limit=${limit}`);
    return response.data;
  },

  async addNewsFlash(newsData) {
    const response = await apiClient.post('/news', newsData);
    return response.data;
  },

  async deleteNewsFlash(broker, title) {
    const response = await apiClient.delete('/news', { data: { broker, title } });
    return response.data;
  },

  async getNewsStatistics() {
    const response = await apiClient.get('/news/statistics');
    return response.data;
  },
};
```

## Core Components

### Broker List Component

Create `src/components/BrokerList.jsx`:

```jsx
import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { brokerApi } from '../services/brokerApi';
import LoadingSpinner from './LoadingSpinner';
import ErrorMessage from './ErrorMessage';

const BrokerList = ({ onBrokerSelect }) => {
  const {
    data: brokers,
    isLoading,
    error,
    refetch
  } = useQuery({
    queryKey: ['brokers'],
    queryFn: brokerApi.getAllBrokers,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorMessage error={error} onRetry={refetch} />;

  return (
    <div className="broker-list">
      <h2 className="text-2xl font-bold mb-4">Belgian Investment Brokers</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {brokers?.brokers?.map((broker) => (
          <BrokerCard 
            key={broker.name}
            broker={broker}
            onSelect={() => onBrokerSelect(broker)}
          />
        ))}
      </div>
      
      <div className="mt-4 text-sm text-gray-600">
        Total brokers: {brokers?.total_count || 0}
        {brokers?.last_updated && (
          <span className="ml-2">
            Last updated: {new Date(brokers.last_updated).toLocaleDateString()}
          </span>
        )}
      </div>
    </div>
  );
};

const BrokerCard = ({ broker, onSelect }) => (
  <div 
    className="border rounded-lg p-4 hover:shadow-lg cursor-pointer transition-shadow"
    onClick={onSelect}
  >
    <div className="flex items-center justify-between mb-2">
      <h3 className="font-semibold">{broker.name}</h3>
      <div className="flex space-x-1">
        {broker.llm_extraction_available && (
          <span className="bg-green-100 text-green-800 text-xs px-2 py-1 rounded">
            AI Extraction
          </span>
        )}
      </div>
    </div>
    
    <p className="text-sm text-gray-600 mb-2">{broker.country}</p>
    
    <div className="flex flex-wrap gap-1 mb-2">
      {broker.instruments.map((instrument) => (
        <span 
          key={instrument}
          className="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded"
        >
          {instrument}
        </span>
      ))}
    </div>
    
    <a 
      href={broker.website}
      target="_blank"
      rel="noopener noreferrer"
      className="text-blue-500 hover:text-blue-700 text-sm"
      onClick={(e) => e.stopPropagation()}
    >
      Visit Website →
    </a>
  </div>
);

export default BrokerList;
```

### Fee Comparison Component

Create `src/components/FeeComparison.jsx`:

```jsx
import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { brokerApi } from '../services/brokerApi';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const FeeComparison = () => {
  const [comparisonParams, setComparisonParams] = useState({
    tradeAmount: 1000,
    instrumentType: 'ETFs',
    selectedBrokers: [],
    includeCustodyFees: false,
  });

  const [availableBrokers, setAvailableBrokers] = useState([]);

  // Fetch available brokers
  const { data: brokersData } = useQuery({
    queryKey: ['brokers'],
    queryFn: brokerApi.getAllBrokers,
    onSuccess: (data) => {
      setAvailableBrokers(data.brokers || []);
    }
  });

  // Run comparison when parameters change
  const {
    data: comparisonResult,
    isLoading: isComparing,
    error: comparisonError,
  } = useQuery({
    queryKey: ['comparison', comparisonParams],
    queryFn: () => brokerApi.compareBrokers({
      trade_amount: comparisonParams.tradeAmount,
      instrument_type: comparisonParams.instrumentType,
      brokers: comparisonParams.selectedBrokers.length > 0 
        ? comparisonParams.selectedBrokers 
        : ['all'],
      include_custody_fees: comparisonParams.includeCustodyFees,
    }),
    enabled: comparisonParams.tradeAmount > 0,
  });

  const handleBrokerToggle = (brokerName) => {
    setComparisonParams(prev => ({
      ...prev,
      selectedBrokers: prev.selectedBrokers.includes(brokerName)
        ? prev.selectedBrokers.filter(b => b !== brokerName)
        : [...prev.selectedBrokers, brokerName]
    }));
  };

  const chartData = comparisonResult?.comparison?.map(item => ({
    broker: item.broker,
    transactionCost: item.transaction_cost,
    custodyCost: item.custody_fee_annual || 0,
    totalCost: item.total_cost,
    rank: item.rank,
  })) || [];

  return (
    <div className="fee-comparison">
      <h2 className="text-2xl font-bold mb-6">Broker Fee Comparison</h2>
      
      {/* Comparison Parameters */}
      <div className="bg-gray-50 p-4 rounded-lg mb-6">
        <h3 className="font-semibold mb-4">Comparison Parameters</h3>
        
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {/* Trade Amount */}
          <div>
            <label className="block text-sm font-medium mb-1">
              Trade Amount (€)
            </label>
            <input
              type="number"
              value={comparisonParams.tradeAmount}
              onChange={(e) => setComparisonParams(prev => ({
                ...prev,
                tradeAmount: parseInt(e.target.value) || 0
              }))}
              className="w-full border rounded px-3 py-2"
              min="1"
              step="100"
            />
          </div>

          {/* Instrument Type */}
          <div>
            <label className="block text-sm font-medium mb-1">
              Instrument Type
            </label>
            <select
              value={comparisonParams.instrumentType}
              onChange={(e) => setComparisonParams(prev => ({
                ...prev,
                instrumentType: e.target.value
              }))}
              className="w-full border rounded px-3 py-2"
            >
              <option value="ETFs">ETFs</option>
              <option value="Equities">Stocks</option>
              <option value="Options">Options</option>
              <option value="Bonds">Bonds</option>
            </select>
          </div>

          {/* Include Custody Fees */}
          <div className="flex items-center">
            <input
              type="checkbox"
              id="includeCustody"
              checked={comparisonParams.includeCustodyFees}
              onChange={(e) => setComparisonParams(prev => ({
                ...prev,
                includeCustodyFees: e.target.checked
              }))}
              className="mr-2"
            />
            <label htmlFor="includeCustody" className="text-sm font-medium">
              Include Annual Custody Fees
            </label>
          </div>
        </div>

        {/* Broker Selection */}
        <div className="mt-4">
          <label className="block text-sm font-medium mb-2">
            Select Brokers (leave empty for all)
          </label>
          <div className="flex flex-wrap gap-2">
            {availableBrokers.map((broker) => (
              <button
                key={broker.name}
                onClick={() => handleBrokerToggle(broker.name)}
                className={`px-3 py-1 rounded text-sm ${
                  comparisonParams.selectedBrokers.includes(broker.name)
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
              >
                {broker.name}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Results */}
      {isComparing && (
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto"></div>
          <p className="mt-2 text-gray-600">Comparing broker fees...</p>
        </div>
      )}

      {comparisonError && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          Error: {comparisonError.message}
        </div>
      )}

      {comparisonResult && !isComparing && (
        <>
          {/* Winner Highlight */}
          {comparisonResult.cheapest && (
            <div className="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded mb-4">
              <strong>🏆 Cheapest Option: {comparisonResult.cheapest.broker}</strong>
              <br />
              You could save €{comparisonResult.cheapest.savings_vs_most_expensive || 0} 
              compared to the most expensive option.
            </div>
          )}

          {/* Comparison Chart */}
          <div className="mb-6">
            <h3 className="font-semibold mb-4">Cost Comparison Chart</h3>
            <ResponsiveContainer width="100%" height={400}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis 
                  dataKey="broker" 
                  angle={-45}
                  textAnchor="end"
                  height={80}
                />
                <YAxis label={{ value: 'Cost (€)', angle: -90, position: 'insideLeft' }} />
                <Tooltip 
                  formatter={(value, name) => [
                    `€${value.toFixed(2)}`, 
                    name === 'transactionCost' ? 'Transaction Cost' :
                    name === 'custodyCost' ? 'Annual Custody Cost' : 'Total Cost'
                  ]}
                />
                <Legend />
                <Bar dataKey="transactionCost" fill="#3B82F6" name="Transaction Cost" />
                {comparisonParams.includeCustodyFees && (
                  <Bar dataKey="custodyCost" fill="#EF4444" name="Custody Cost" />
                )}
                <Bar dataKey="totalCost" fill="#10B981" name="Total Cost" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Detailed Results Table */}
          <div className="overflow-x-auto">
            <table className="min-w-full border-collapse border border-gray-300">
              <thead className="bg-gray-50">
                <tr>
                  <th className="border border-gray-300 px-4 py-2 text-left">Rank</th>
                  <th className="border border-gray-300 px-4 py-2 text-left">Broker</th>
                  <th className="border border-gray-300 px-4 py-2 text-right">Transaction Cost</th>
                  <th className="border border-gray-300 px-4 py-2 text-right">Custody Cost (Annual)</th>
                  <th className="border border-gray-300 px-4 py-2 text-right">Total Cost</th>
                </tr>
              </thead>
              <tbody>
                {comparisonResult.comparison.map((result) => (
                  <tr 
                    key={result.broker}
                    className={result.rank === 1 ? 'bg-green-50 font-semibold' : ''}
                  >
                    <td className="border border-gray-300 px-4 py-2">
                      {result.rank === 1 && '🏆'} #{result.rank}
                    </td>
                    <td className="border border-gray-300 px-4 py-2">{result.broker}</td>
                    <td className="border border-gray-300 px-4 py-2 text-right">
                      €{result.transaction_cost.toFixed(2)}
                    </td>
                    <td className="border border-gray-300 px-4 py-2 text-right">
                      €{(result.custody_fee_annual || 0).toFixed(2)}
                    </td>
                    <td className="border border-gray-300 px-4 py-2 text-right">
                      €{result.total_cost.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
};

export default FeeComparison;
```

## Investment Scenarios

Create `src/components/InvestmentScenarios.jsx`:

```jsx
import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { brokerApi } from '../services/brokerApi';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const InvestmentScenarios = () => {
  const [scenarios, setScenarios] = useState([
    {
      name: 'Monthly Investor',
      lump_sum: 0,
      monthly_investment: 169,
      duration_years: 5,
      instrument_types: ['ETFs', 'Equities']
    },
    {
      name: 'High Value Investor', 
      lump_sum: 10000,
      monthly_investment: 500,
      duration_years: 5,
      instrument_types: ['ETFs']
    }
  ]);

  const [customScenario, setCustomScenario] = useState({
    name: 'Custom Scenario',
    lump_sum: 5000,
    monthly_investment: 300,
    duration_years: 3,
    instrument_types: ['ETFs']
  });

  const {
    data: scenarioResults,
    isLoading,
    error,
    refetch
  } = useQuery({
    queryKey: ['scenarios', scenarios],
    queryFn: () => brokerApi.analyzeScenarios({
      scenarios: scenarios,
      brokers: ['all']
    }),
    enabled: scenarios.length > 0,
  });

  const addCustomScenario = () => {
    setScenarios(prev => [...prev, { ...customScenario }]);
    setCustomScenario({
      name: 'Custom Scenario',
      lump_sum: 5000,
      monthly_investment: 300,
      duration_years: 3,
      instrument_types: ['ETFs']
    });
  };

  const removeScenario = (index) => {
    setScenarios(prev => prev.filter((_, i) => i !== index));
  };

  // Prepare chart data
  const chartData = scenarioResults?.scenarios?.flatMap(scenario => 
    Object.entries(scenario.results).flatMap(([instrumentType, results]) =>
      results.map(result => ({
        scenario: scenario.name,
        instrumentType,
        broker: result.broker,
        totalCost: result.total_cost,
        rank: result.rank
      }))
    )
  ) || [];

  return (
    <div className="investment-scenarios">
      <h2 className="text-2xl font-bold mb-6">Investment Scenario Analysis</h2>

      {/* Current Scenarios */}
      <div className="mb-6">
        <h3 className="text-lg font-semibold mb-4">Current Scenarios</h3>
        <div className="space-y-4">
          {scenarios.map((scenario, index) => (
            <div key={index} className="bg-gray-50 p-4 rounded-lg flex justify-between items-center">
              <div>
                <h4 className="font-medium">{scenario.name}</h4>
                <p className="text-sm text-gray-600">
                  Lump sum: €{scenario.lump_sum.toLocaleString()} | 
                  Monthly: €{scenario.monthly_investment} | 
                  Duration: {scenario.duration_years} years |
                  Instruments: {scenario.instrument_types.join(', ')}
                </p>
                <p className="text-xs text-gray-500">
                  Total invested: €{(scenario.lump_sum + (scenario.monthly_investment * scenario.duration_years * 12)).toLocaleString()}
                </p>
              </div>
              <button
                onClick={() => removeScenario(index)}
                className="text-red-500 hover:text-red-700"
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Add Custom Scenario */}
      <div className="bg-blue-50 p-4 rounded-lg mb-6">
        <h3 className="text-lg font-semibold mb-4">Add Custom Scenario</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
          <div>
            <label className="block text-sm font-medium mb-1">Scenario Name</label>
            <input
              type="text"
              value={customScenario.name}
              onChange={(e) => setCustomScenario(prev => ({ ...prev, name: e.target.value }))}
              className="w-full border rounded px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Lump Sum (€)</label>
            <input
              type="number"
              value={customScenario.lump_sum}
              onChange={(e) => setCustomScenario(prev => ({ ...prev, lump_sum: parseInt(e.target.value) || 0 }))}
              className="w-full border rounded px-3 py-2"
              min="0"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Monthly Investment (€)</label>
            <input
              type="number"
              value={customScenario.monthly_investment}
              onChange={(e) => setCustomScenario(prev => ({ ...prev, monthly_investment: parseInt(e.target.value) || 0 }))}
              className="w-full border rounded px-3 py-2"
              min="0"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Duration (Years)</label>
            <input
              type="number"
              value={customScenario.duration_years}
              onChange={(e) => setCustomScenario(prev => ({ ...prev, duration_years: parseInt(e.target.value) || 1 }))}
              className="w-full border rounded px-3 py-2"
              min="1"
              max="50"
            />
          </div>
        </div>
        <div className="mb-4">
          <label className="block text-sm font-medium mb-1">Instrument Types</label>
          <div className="flex space-x-4">
            {['ETFs', 'Equities', 'Options', 'Bonds'].map(type => (
              <label key={type} className="flex items-center">
                <input
                  type="checkbox"
                  checked={customScenario.instrument_types.includes(type)}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setCustomScenario(prev => ({
                        ...prev,
                        instrument_types: [...prev.instrument_types, type]
                      }));
                    } else {
                      setCustomScenario(prev => ({
                        ...prev,
                        instrument_types: prev.instrument_types.filter(t => t !== type)
                      }));
                    }
                  }}
                  className="mr-2"
                />
                {type}
              </label>
            ))}
          </div>
        </div>
        <button
          onClick={addCustomScenario}
          className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600"
          disabled={!customScenario.name || customScenario.instrument_types.length === 0}
        >
          Add Scenario
        </button>
      </div>

      {/* Results */}
      {isLoading && (
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto"></div>
          <p className="mt-2 text-gray-600">Analyzing investment scenarios...</p>
        </div>
      )}

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          Error: {error.message}
          <button onClick={refetch} className="ml-2 underline">Retry</button>
        </div>
      )}

      {scenarioResults && !isLoading && (
        <>
          {/* Results Chart */}
          <div className="mb-6">
            <h3 className="text-lg font-semibold mb-4">Total Cost Comparison</h3>
            <ResponsiveContainer width="100%" height={400}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="broker" />
                <YAxis label={{ value: 'Total Cost (€)', angle: -90, position: 'insideLeft' }} />
                <Tooltip formatter={(value) => [`€${value.toFixed(2)}`, 'Total Cost']} />
                <Legend />
                {scenarios.map((scenario, index) => (
                  <Line
                    key={scenario.name}
                    type="monotone"
                    dataKey="totalCost"
                    stroke={['#3B82F6', '#EF4444', '#10B981', '#F59E0B'][index % 4]}
                    name={scenario.name}
                    data={chartData.filter(d => d.scenario === scenario.name)}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Detailed Results */}
          <div className="space-y-6">
            {scenarioResults.scenarios.map((scenario) => (
              <div key={scenario.name} className="border rounded-lg p-4">
                <h3 className="text-lg font-semibold mb-4">{scenario.name}</h3>
                
                {Object.entries(scenario.results).map(([instrumentType, results]) => (
                  <div key={instrumentType} className="mb-4">
                    <h4 className="font-medium text-blue-600 mb-2">{instrumentType}</h4>
                    
                    <div className="overflow-x-auto">
                      <table className="min-w-full text-sm border-collapse border border-gray-300">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="border border-gray-300 px-3 py-2 text-left">Rank</th>
                            <th className="border border-gray-300 px-3 py-2 text-left">Broker</th>
                            <th className="border border-gray-300 px-3 py-2 text-right">Transaction Cost</th>
                            <th className="border border-gray-300 px-3 py-2 text-right">Custody Cost</th>
                            <th className="border border-gray-300 px-3 py-2 text-right">Total Cost</th>
                            <th className="border border-gray-300 px-3 py-2 text-right">Cost %</th>
                          </tr>
                        </thead>
                        <tbody>
                          {results.map((result) => {
                            const totalInvested = scenario.lump_sum + (scenario.monthly_investment * scenario.duration_years * 12);
                            const costPercentage = (result.total_cost / totalInvested) * 100;
                            
                            return (
                              <tr 
                                key={result.broker}
                                className={result.rank === 1 ? 'bg-green-50 font-medium' : ''}
                              >
                                <td className="border border-gray-300 px-3 py-2">
                                  {result.rank === 1 && '🏆'} #{result.rank}
                                </td>
                                <td className="border border-gray-300 px-3 py-2">{result.broker}</td>
                                <td className="border border-gray-300 px-3 py-2 text-right">
                                  €{result.total_transaction_cost.toFixed(2)}
                                </td>
                                <td className="border border-gray-300 px-3 py-2 text-right">
                                  €{result.total_custody_cost.toFixed(2)}
                                </td>
                                <td className="border border-gray-300 px-3 py-2 text-right">
                                  €{result.total_cost.toFixed(2)}
                                </td>
                                <td className="border border-gray-300 px-3 py-2 text-right">
                                  {costPercentage.toFixed(2)}%
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
};

export default InvestmentScenarios;
```

## Real-time Features

Create `src/hooks/useWebSocket.js`:

```javascript
// WebSocket hook for real-time updates
import { useEffect, useRef, useState } from 'react';

export const useWebSocket = (url) => {
  const [data, setData] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState('Connecting');
  const ws = useRef(null);

  useEffect(() => {
    const wsUrl = url.replace('http', 'ws');
    ws.current = new WebSocket(`${wsUrl}/ws`);

    ws.current.onopen = () => {
      setConnectionStatus('Connected');
      // Subscribe to updates
      ws.current.send(JSON.stringify({
        type: 'subscribe',
        topics: ['extractions', 'validations', 'analysis']
      }));
    };

    ws.current.onmessage = (event) => {
      const message = JSON.parse(event.data);
      setData(message);
    };

    ws.current.onclose = () => {
      setConnectionStatus('Disconnected');
    };

    ws.current.onerror = () => {
      setConnectionStatus('Error');
    };

    return () => {
      ws.current?.close();
    };
  }, [url]);

  const sendMessage = (message) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(message));
    }
  };

  return { data, connectionStatus, sendMessage };
};
```

Create `src/components/RealTimeUpdates.jsx`:

```jsx
import React, { useState, useEffect } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';

const RealTimeUpdates = () => {
  const [updates, setUpdates] = useState([]);
  const { data, connectionStatus } = useWebSocket(process.env.REACT_APP_API_BASE_URL);

  useEffect(() => {
    if (data) {
      setUpdates(prev => [data, ...prev.slice(0, 19)]); // Keep last 20 updates
    }
  }, [data]);

  const getUpdateIcon = (type) => {
    switch (type) {
      case 'extraction_completed': return '✅';
      case 'extraction_failed': return '❌';
      case 'validation_completed': return '🔍';
      case 'analysis_updated': return '📊';
      default: return 'ℹ️';
    }
  };

  const getUpdateColor = (type) => {
    switch (type) {
      case 'extraction_completed': return 'text-green-600';
      case 'extraction_failed': return 'text-red-600';
      case 'validation_completed': return 'text-blue-600';
      case 'analysis_updated': return 'text-purple-600';
      default: return 'text-gray-600';
    }
  };

  return (
    <div className="real-time-updates">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">Real-time Updates</h3>
        <div className="flex items-center">
          <div className={`w-3 h-3 rounded-full mr-2 ${
            connectionStatus === 'Connected' ? 'bg-green-500' :
            connectionStatus === 'Connecting' ? 'bg-yellow-500' : 'bg-red-500'
          }`}></div>
          <span className="text-sm text-gray-600">{connectionStatus}</span>
        </div>
      </div>

      <div className="max-h-96 overflow-y-auto space-y-2">
        {updates.length === 0 ? (
          <p className="text-gray-500 text-center py-4">No updates yet...</p>
        ) : (
          updates.map((update, index) => (
            <div key={index} className="bg-gray-50 p-3 rounded border-l-4 border-blue-500">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center mb-1">
                    <span className="text-lg mr-2">{getUpdateIcon(update.type)}</span>
                    <span className={`font-medium ${getUpdateColor(update.type)}`}>
                      {update.type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                    </span>
                  </div>
                  
                  {update.broker && (
                    <p className="text-sm text-gray-700">Broker: {update.broker}</p>
                  )}
                  
                  {update.records_extracted && (
                    <p className="text-sm text-gray-700">
                      Records extracted: {update.records_extracted}
                    </p>
                  )}
                  
                  {update.message && (
                    <p className="text-sm text-gray-700">{update.message}</p>
                  )}
                </div>
                
                <span className="text-xs text-gray-500 ml-2">
                  {new Date(update.timestamp).toLocaleTimeString()}
                </span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default RealTimeUpdates;
```

## State Management

Create `src/context/BrokerContext.js`:

```javascript
// Global state management for broker data
import React, { createContext, useContext, useReducer } from 'react';

const BrokerContext = createContext();

const initialState = {
  brokers: [],
  selectedBrokers: [],
  comparisonResults: null,
  scenarioResults: null,
  loading: {
    brokers: false,
    comparison: false,
    scenarios: false,
  },
  errors: {
    brokers: null,
    comparison: null,
    scenarios: null,
  },
  preferences: {
    defaultInstrumentType: 'ETFs',
    defaultTradeAmount: 1000,
    includeCustodyFees: false,
  },
};

const brokerReducer = (state, action) => {
  switch (action.type) {
    case 'SET_BROKERS':
      return {
        ...state,
        brokers: action.payload,
        loading: { ...state.loading, brokers: false },
        errors: { ...state.errors, brokers: null },
      };

    case 'SET_LOADING':
      return {
        ...state,
        loading: { ...state.loading, [action.payload.type]: action.payload.loading },
      };

    case 'SET_ERROR':
      return {
        ...state,
        errors: { ...state.errors, [action.payload.type]: action.payload.error },
        loading: { ...state.loading, [action.payload.type]: false },
      };

    case 'SET_SELECTED_BROKERS':
      return {
        ...state,
        selectedBrokers: action.payload,
      };

    case 'SET_COMPARISON_RESULTS':
      return {
        ...state,
        comparisonResults: action.payload,
        loading: { ...state.loading, comparison: false },
        errors: { ...state.errors, comparison: null },
      };

    case 'SET_SCENARIO_RESULTS':
      return {
        ...state,
        scenarioResults: action.payload,
        loading: { ...state.loading, scenarios: false },
        errors: { ...state.errors, scenarios: null },
      };

    case 'UPDATE_PREFERENCES':
      return {
        ...state,
        preferences: { ...state.preferences, ...action.payload },
      };

    case 'RESET_STATE':
      return initialState;

    default:
      return state;
  }
};

export const BrokerProvider = ({ children }) => {
  const [state, dispatch] = useReducer(brokerReducer, initialState);

  return (
    <BrokerContext.Provider value={{ state, dispatch }}>
      {children}
    </BrokerContext.Provider>
  );
};

export const useBroker = () => {
  const context = useContext(BrokerContext);
  if (!context) {
    throw new Error('useBroker must be used within a BrokerProvider');
  }
  return context;
};

// Action creators
export const brokerActions = {
  setBrokers: (brokers) => ({ type: 'SET_BROKERS', payload: brokers }),
  setLoading: (type, loading) => ({ type: 'SET_LOADING', payload: { type, loading } }),
  setError: (type, error) => ({ type: 'SET_ERROR', payload: { type, error } }),
  setSelectedBrokers: (brokers) => ({ type: 'SET_SELECTED_BROKERS', payload: brokers }),
  setComparisonResults: (results) => ({ type: 'SET_COMPARISON_RESULTS', payload: results }),
  setScenarioResults: (results) => ({ type: 'SET_SCENARIO_RESULTS', payload: results }),
  updatePreferences: (preferences) => ({ type: 'UPDATE_PREFERENCES', payload: preferences }),
  resetState: () => ({ type: 'RESET_STATE' }),
};
```

## Error Handling

Create `src/components/ErrorBoundary.jsx`:

```jsx
import React from 'react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50">
          <div className="max-w-md mx-auto text-center">
            <div className="mb-4">
              <div className="mx-auto w-12 h-12 bg-red-100 rounded-full flex items-center justify-center">
                <span className="text-red-600 text-2xl">⚠️</span>
              </div>
            </div>
            <h1 className="text-xl font-semibold text-gray-900 mb-2">
              Something went wrong
            </h1>
            <p className="text-gray-600 mb-4">
              We're sorry, but something unexpected happened. Please try refreshing the page.
            </p>
            <button
              onClick={() => window.location.reload()}
              className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600"
            >
              Refresh Page
            </button>
            {process.env.NODE_ENV === 'development' && (
              <details className="mt-4 text-left text-sm">
                <summary className="cursor-pointer text-gray-700 font-medium">
                  Error Details (Development)
                </summary>
                <pre className="mt-2 p-2 bg-gray-100 rounded overflow-x-auto">
                  {this.state.error?.toString()}
                </pre>
              </details>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
```

## Performance Optimization

Create `src/hooks/useDebounce.js`:

```javascript
// Debounce hook for API calls
import { useState, useEffect } from 'react';

export const useDebounce = (value, delay) => {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
};
```

Create `src/hooks/useLocalStorage.js`:

```javascript
// Local storage hook for persisting user preferences
import { useState, useEffect } from 'react';

export const useLocalStorage = (key, initialValue) => {
  const [storedValue, setStoredValue] = useState(() => {
    try {
      const item = window.localStorage.getItem(key);
      return item ? JSON.parse(item) : initialValue;
    } catch (error) {
      console.error(`Error reading localStorage key "${key}":`, error);
      return initialValue;
    }
  });

  const setValue = (value) => {
    try {
      const valueToStore = value instanceof Function ? value(storedValue) : value;
      setStoredValue(valueToStore);
      window.localStorage.setItem(key, JSON.stringify(valueToStore));
    } catch (error) {
      console.error(`Error setting localStorage key "${key}":`, error);
    }
  };

  return [storedValue, setValue];
};
```

## TypeScript Support

Create `src/types/api.ts`:

```typescript
// TypeScript type definitions for API responses
export interface Broker {
  name: string;
  website: string;
  country: string;
  instruments: string[];
  llm_extraction_available: boolean;
  last_updated?: string;
}

export interface FeeRecord {
  broker: string;
  instrument_type: string;
  order_channel: string;
  base_fee: number | null;
  variable_fee: string | null;
  currency: string;
  source: string;
  notes?: string;
}

export interface ComparisonRequest {
  trade_amount: number;
  instrument_type: string;
  brokers: string[];
  include_custody_fees: boolean;
}

export interface ComparisonResult {
  broker: string;
  transaction_cost: number;
  custody_fee_annual: number;
  total_cost: number;
  rank: number;
}

export interface ComparisonResponse {
  trade_amount: number;
  instrument_type: string;
  comparison: ComparisonResult[];
  cheapest: {
    broker: string;
    savings_vs_most_expensive: number;
  };
}

export interface InvestmentScenario {
  name: string;
  lump_sum: number;
  monthly_investment: number;
  duration_years: number;
  instrument_types: string[];
}

export interface ScenarioResult {
  broker: string;
  total_transaction_cost: number;
  total_custody_cost: number;
  total_cost: number;
  rank: number;
}

export interface ScenarioResponse {
  scenarios: Array<{
    name: string;
    results: {
      [instrumentType: string]: ScenarioResult[];
    };
  }>;
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: any;
    timestamp: string;
    request_id: string;
  };
}
```

## Main App Component

Create `src/App.jsx`:

```jsx
import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import ErrorBoundary from './components/ErrorBoundary';
import { BrokerProvider } from './context/BrokerContext';
import BrokerDashboard from './components/BrokerDashboard';
import './App.css';

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      cacheTime: 10 * 60 * 1000, // 10 minutes
      retry: (failureCount, error) => {
        // Don't retry for 4xx errors
        if (error?.response?.status >= 400 && error?.response?.status < 500) {
          return false;
        }
        return failureCount < 3;
      },
    },
  },
});

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrokerProvider>
          <div className="App min-h-screen bg-gray-50">
            <header className="bg-white shadow">
              <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex justify-between items-center py-6">
                  <div className="flex items-center">
                    <h1 className="text-3xl font-bold text-gray-900">
                      🇧🇪 BE-Invest
                    </h1>
                    <span className="ml-3 px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm">
                      Belgian Broker Comparison
                    </span>
                  </div>
                  <div className="flex items-center space-x-4">
                    <a
                      href={`${process.env.REACT_APP_API_BASE_URL}/docs`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:text-blue-800"
                    >
                      API Docs
                    </a>
                    <a
                      href="https://github.com/your-username/be-invest"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-gray-600 hover:text-gray-800"
                    >
                      GitHub
                    </a>
                  </div>
                </div>
              </div>
            </header>

            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
              <BrokerDashboard />
            </main>

            <footer className="bg-white border-t mt-16">
              <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <div className="text-center text-gray-600 text-sm">
                  <p>
                    BE-Invest - Belgian Investment Broker Fee Comparison Tool
                  </p>
                  <p className="mt-2">
                    Data extracted from official broker documents. 
                    Always verify fees directly with brokers before making investment decisions.
                  </p>
                </div>
              </div>
            </footer>
          </div>
        </BrokerProvider>
        
        {process.env.NODE_ENV === 'development' && <ReactQueryDevtools />}
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
```

## Usage Examples

### Basic Integration

```jsx
// Simple broker comparison component
import { useState } from 'react';
import { brokerApi } from '../services/brokerApi';

const SimpleBrokerComparison = () => {
  const [comparison, setComparison] = useState(null);
  
  const compareETFs = async () => {
    try {
      const result = await brokerApi.compareBrokers({
        trade_amount: 1000,
        instrument_type: 'ETFs',
        brokers: ['all'],
        include_custody_fees: false
      });
      setComparison(result);
    } catch (error) {
      console.error('Comparison failed:', error);
    }
  };

  return (
    <div>
      <button onClick={compareETFs}>
        Compare ETF Costs for €1000 Trade
      </button>
      
      {comparison && (
        <div>
          <h3>Best Option: {comparison.cheapest.broker}</h3>
          <ul>
            {comparison.comparison.map(result => (
              <li key={result.broker}>
                {result.broker}: €{result.total_cost}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};
```

### Advanced Integration with React Query

```jsx
// Advanced component with caching and error handling
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

const AdvancedBrokerAnalysis = () => {
  const queryClient = useQueryClient();
  
  // Fetch brokers with caching
  const { data: brokers } = useQuery({
    queryKey: ['brokers'],
    queryFn: brokerApi.getAllBrokers,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });

  // Comparison mutation
  const comparisonMutation = useMutation({
    mutationFn: brokerApi.compareBrokers,
    onSuccess: (data) => {
      // Cache the result
      queryClient.setQueryData(['comparison', data.trade_amount], data);
    },
  });

  const handleCompare = (params) => {
    comparisonMutation.mutate(params);
  };

  return (
    <div>
      {/* Your component JSX */}
      <ComparisonForm onSubmit={handleCompare} />
      
      {comparisonMutation.isLoading && <LoadingSpinner />}
      {comparisonMutation.error && <ErrorMessage error={comparisonMutation.error} />}
      {comparisonMutation.data && <ComparisonResults data={comparisonMutation.data} />}
    </div>
  );
};
```

## Integration Checklist

### ✅ Setup Tasks
- [ ] Install required dependencies (`axios`, `@tanstack/react-query`)
- [ ] Configure environment variables (API base URL)
- [ ] Set up API client with error handling
- [ ] Add React Query provider to app root

### ✅ Core Features Integration
- [ ] Broker listing and selection
- [ ] Fee comparison functionality
- [ ] Investment scenario analysis
- [ ] Real-time updates (WebSocket)
- [ ] Error boundary for graceful error handling

### ✅ User Experience
- [ ] Loading states for all API calls
- [ ] Error messages with retry options
- [ ] Responsive design for mobile devices
- [ ] Accessibility features (ARIA labels)

### ✅ Performance
- [ ] Query caching with React Query
- [ ] Debounced search/filter inputs
- [ ] Local storage for user preferences
- [ ] Optimized re-renders with React.memo

### ✅ Production Ready
- [ ] TypeScript types for better development
- [ ] Error tracking and monitoring
- [ ] Analytics integration
- [ ] SEO optimization

---

This comprehensive React integration guide provides everything needed to build a full-featured frontend application with all BE-Invest API functionalities. The examples show both simple and advanced patterns, allowing developers to choose the appropriate level of complexity for their needs.
