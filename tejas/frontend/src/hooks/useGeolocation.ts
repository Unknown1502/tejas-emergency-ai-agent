/**
 * React hook for accessing device geolocation.
 *
 * Provides GPS coordinates for incident reporting and tool
 * calls that require location context (dispatch, hospital lookup).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { GeoLocation } from "../types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface UseGeolocationReturn {
  /** Current location, or null if not yet obtained. */
  location: GeoLocation | null;
  /** Whether location is being actively tracked. */
  isTracking: boolean;
  /** Error message if geolocation failed. */
  error: string | null;
  /** Request a single location fix. */
  requestLocation: () => void;
  /** Start continuous location tracking. */
  startTracking: () => void;
  /** Stop continuous tracking. */
  stopTracking: () => void;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useGeolocation(): UseGeolocationReturn {
  const [location, setLocation] = useState<GeoLocation | null>(null);
  const [isTracking, setIsTracking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const watchIdRef = useRef<number | null>(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (watchIdRef.current !== null) {
        navigator.geolocation.clearWatch(watchIdRef.current);
      }
    };
  }, []);

  const handlePosition = useCallback((position: GeolocationPosition) => {
    setLocation({
      latitude: position.coords.latitude,
      longitude: position.coords.longitude,
      accuracy: position.coords.accuracy,
      timestamp: position.timestamp,
    });
    setError(null);
  }, []);

  const handleError = useCallback((err: GeolocationPositionError) => {
    switch (err.code) {
      case err.PERMISSION_DENIED:
        setError("Location permission denied.");
        break;
      case err.POSITION_UNAVAILABLE:
        setError("Location information unavailable.");
        break;
      case err.TIMEOUT:
        setError("Location request timed out.");
        break;
      default:
        setError("Unknown geolocation error.");
    }
  }, []);

  const requestLocation = useCallback(() => {
    if (!navigator.geolocation) {
      setError("Geolocation is not supported by this browser.");
      return;
    }

    navigator.geolocation.getCurrentPosition(handlePosition, handleError, {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 30000,
    });
  }, [handlePosition, handleError]);

  const startTracking = useCallback(() => {
    if (!navigator.geolocation) {
      setError("Geolocation is not supported by this browser.");
      return;
    }

    // Clear any existing watch
    if (watchIdRef.current !== null) {
      navigator.geolocation.clearWatch(watchIdRef.current);
    }

    watchIdRef.current = navigator.geolocation.watchPosition(
      handlePosition,
      handleError,
      {
        enableHighAccuracy: true,
        timeout: 15000,
        maximumAge: 10000,
      }
    );

    setIsTracking(true);
  }, [handlePosition, handleError]);

  const stopTracking = useCallback(() => {
    if (watchIdRef.current !== null) {
      navigator.geolocation.clearWatch(watchIdRef.current);
      watchIdRef.current = null;
    }
    setIsTracking(false);
  }, []);

  return {
    location,
    isTracking,
    error,
    requestLocation,
    startTracking,
    stopTracking,
  };
}
