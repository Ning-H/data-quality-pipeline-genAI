 CREATE OR REPLACE EXTERNAL TABLE `nyc-taxi-trust-layer.nyc_taxi_trust.yellow_trips_external`                
  WITH CONNECTION `nyc-taxi-trust-layer.us.f8b500bd-4da3-4023-8919-02fc2915d682`
  OPTIONS (                                                                                                   
    format = 'ICEBERG',
    uris = ['gs://nyc-taxi-trust-layer-warehouse/warehouse/yellow_taxi/trips/metadata/v5.metadata.json']      
  );                                                                                                          
  
