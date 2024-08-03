// To run this : uvicorn main:app --reload

import { useState, useEffect } from "react";
import axios from "axios";
import "tailwindcss/tailwind.css";
import Modal from "./components/Modal";
import { FaArrowRight, FaCheckCircle, FaSpinner } from "react-icons/fa"; // Import FaSpinner

function App() {
  const [awsAccessKeyId, setAwsAccessKeyId] = useState("");
  const [awsSecretAccessKey, setAwsSecretAccessKey] = useState(
    ""
  );
  const [regionName, setRegionName] = useState("");
  const [instances, setInstances] = useState([]);
  const [selectedInstances, setSelectedInstances] = useState([]);
  const [vpcs, setVpcs] = useState([]);
  const [selectedVpc, setSelectedVpc] = useState("");
  const [isModalOpen, setIsModalOpen] = useState(false);

  const [destAccountId, setDestAccountId] = useState("");
  const [awsDestAccessKeyId, setAwsDestAccessKeyId] = useState(
    ""
  );
  const [awsDestSecretAccessKey, setAwsDestSecretAccessKey] = useState(
    ""
  );
  const [destRegionName, setDestRegionName] = useState("");
  const [subnets, setSubnets] = useState([]);
  const [selectedSubnet, setSelectedSubnet] = useState("");
  const [securityGroups, setSecurityGroups] = useState([]);
  const [selectedSecurityGroup, setSelectedSecurityGroup] = useState("");
  const [isDone, setIsDone] = useState(false);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [isLoading, setIsLoading] = useState(false); // Add loading state
  const [isMigrationDone, setISMigrationDone] = useState(false);

  //Object to store modal info: title: "VPC", Description: "Select an exsi....", Data: vpcs, selectedData: selectedVpc, setSelectedData: setSelectedVpc, isOpen: isModalOpen, setIsOpen: setIsModalOpen
  const vpcModal = {
    title: "VPC",
    description: `Select an existing VPC or click on the "create new" button to create a new one`,
    data: vpcs,
    selectedData: selectedVpc,
    setSelectedData: setSelectedVpc,
    isOpen: isModalOpen,
    setIsOpen: setIsModalOpen,
  };
  const subnetModal = {
    title: "Subnet",
    description: `Select an existing Subnet or click on the "create new" button to create a new one`,
    data: subnets,
    selectedData: selectedSubnet,
    setSelectedData: setSelectedSubnet,
    isOpen: isModalOpen,
    setIsOpen: setIsModalOpen,
  };

  const securityGroupModal = {
    title: "Security Group",
    description: `Select an existing Security Group or click on the "create new" button to create a new one`,
    data: securityGroups,
    selectedData: selectedSecurityGroup,
    setSelectedData: setSelectedSecurityGroup,
    isOpen: isModalOpen,
    setIsOpen: setIsModalOpen,
  };

  //An array of modals
  const modals = [vpcModal, subnetModal, securityGroupModal];

  const handleListInstances = async () => {
    try {
      const response = await axios.post(
        "http://localhost:8000/list-instances",
        {
          aws_access_key_id: awsAccessKeyId,
          aws_secret_access_key: awsSecretAccessKey,
          region_name: regionName,
          vpc_id: "", // we don't need Vpc ID for this
        }
      );
      setInstances(response.data.instances);
    } catch (error) {
      console.error("Error listing instances:", error);
    }
  };

  const handleSelectInstance = (instanceId) => {
    if (selectedInstances.includes(instanceId)) {
      setSelectedInstances(selectedInstances.filter((id) => id !== instanceId));
    } else {
      setSelectedInstances([...selectedInstances, instanceId]);
    }
  };

  useEffect(() => {
    if (selectedInstances.length != 0) {
      console.log("Selected instances:", selectedInstances);
    }
  }, [selectedInstances]);

  const handleMigration = () => {
    if (selectedInstances.length == 0) {
      alert("Please select at least one instance to migrate");
      return;
    }
    setIsModalOpen(true);
    handleListVpcs();
    // we need to wait until a vpc is selected before we can list subnets and security groups
  };
  const handle_migrate_resources = async () => {
    setIsLoading(true); // Start loading
    try {
      // Create an array of promises for each migration task
      const migrationPromises = selectedInstances.map((instance) => {
        return axios.post("http://localhost:8000/migrate-instance", {
          source_aws_access_key_id: awsAccessKeyId,
          source_aws_secret_access_key: awsSecretAccessKey,
          source_region_name: regionName,
          dest_account_id: destAccountId,
          dest_aws_access_key_id: awsDestAccessKeyId,
          dest_aws_secret_access_key: awsDestSecretAccessKey,
          dest_region_name: destRegionName,
          instance_id: instance, // This needs to be a single ID if that is the expectation
          selected_vpc_id: selectedVpc,
          selected_subnet_id: selectedSubnet,
          selected_security_group_id: selectedSecurityGroup,
        });
      });

      // Wait for all migrations to complete
      await Promise.all(migrationPromises);
      console.log("All instances migrated successfully");
      setISMigrationDone(true);
    } catch (error) {
      console.error("Error migrating resources:", error);
    } finally {
      setIsLoading(false); // Stop loading
    }
  };

  const handleListVpcs = async () => {
    try {
      const response = await axios.post("http://localhost:8000/list-vpcs", {
        aws_access_key_id: awsDestAccessKeyId,
        aws_secret_access_key: awsDestSecretAccessKey,
        region_name: destRegionName,
        vpc_id: "", // we don't need Vpc ID for this
      });
      setVpcs(response.data.vpcs);
      // console.log("VPCs:", response.data.vpcs);
    } catch (error) {
      console.error("Error listing VPCs:", error);
    }
  };

  useEffect(() => {
    if (selectedVpc != "" && selectedVpc != "create new") {
      handleListSubnets();
      handleListSecurityGroups();
    }
    if (selectedVpc == "create new") {
      // reset the subnet and security group
      setSubnets([]);
      setSecurityGroups([]);
    }
  }, [selectedVpc]);

  const handleListSubnets = async () => {
    try {
      const response = await axios.post("http://localhost:8000/list-subnets", {
        aws_access_key_id: awsDestAccessKeyId,
        aws_secret_access_key: awsDestSecretAccessKey,
        region_name: destRegionName,
        vpc_id: selectedVpc,
      });
      setSubnets(response.data.subnets);
      // console.log("Subnets:", response.data.subnets);
    } catch (error) {
      console.error("Error listing Subnets:", error);
    }
  };

  const handleListSecurityGroups = async () => {
    try {
      const response = await axios.post(
        "http://localhost:8000/list-security-groups",
        {
          aws_access_key_id: awsDestAccessKeyId,
          aws_secret_access_key: awsDestSecretAccessKey,
          region_name: destRegionName,
          vpc_id: selectedVpc,
        }
      );
      setSecurityGroups(response.data.security_groups);
      // console.log("Security Groups:", response.data.security_groups);
    } catch (error) {
      console.error("Error listing Security Groups:", error);
    }
  };

  const handleDone = () => {
    setIsModalOpen(false);
    setIsDone(false);
    setCurrentIdx(0);
    handle_migrate_resources();
    //the logic for executing :create AMI & Launch EC2 instance
  };

  const handleCancel = () => {
    setIsModalOpen(false);
    setIsDone(false);
    setCurrentIdx(0);
  };

  return (
    <div className="flex-row items-center space-y-9 justify-center h-screen bg-gray-100">
      <h1 className="text-2xl py-8 font-bold text-center">
        AWS Resources Migration Between Accounts
      </h1>

      <div className="min-w-max flex flex-row space-x-10 items-center justify-center">
        <div className="w-custom min-h-custom p-8 space-y-8 bg-white rounded-lg shadow-md">
          <h1>Scan the resources in your source account</h1>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">
                AWS Access Key ID
              </label>
              <input
                type="text"
                value={awsAccessKeyId}
                onChange={(e) => setAwsAccessKeyId(e.target.value)}
                className="w-full px-3 py-2 mt-1 border rounded-md focus:outline-none focus:ring focus:border-blue-300"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">
                AWS Secret Access Key
              </label>
              <input
                type="password"
                value={awsSecretAccessKey}
                onChange={(e) => setAwsSecretAccessKey(e.target.value)}
                className="w-full px-3 py-2 mt-1 border rounded-md focus:outline-none focus:ring focus:border-blue-300"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Region Name
              </label>
              <input
                type="text"
                value={regionName}
                onChange={(e) => setRegionName(e.target.value)}
                className="w-full px-3 py-2 mt-1 border rounded-md focus:outline-none focus:ring focus:border-blue-300"
              />
            </div>

            <button
              onClick={handleListInstances}
              className="w-full px-4 py-2 mt-4 font-bold text-white bg-blue-500 rounded-md hover:bg-blue-600 focus:outline-none focus:ring focus:border-blue-300"
            >
              List Instances
            </button>
          </div>
          <ul className="mt-4 space-y-2">
            {instances.map((id, index) => (
              <li
                key={index}
                className="flex items-center justify-between bg-slate-100 p-2 rounded-md"
              >
                <span>{id}</span>
                <input
                  type="checkbox"
                  onChange={() => handleSelectInstance(id)}
                  checked={selectedInstances.includes(id)}
                />
              </li>
            ))}
          </ul>
        </div>

        <div className="flex items-center justify-center">
          <FaArrowRight className="text-4xl text-gray-500" />
        </div>

        <div className="w-custom min-h-custom p-8 space-y-8 bg-white rounded-lg shadow-md">
          <h1>Destination Account</h1>

          <div className="space-y-4">
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  AWS Account ID
                </label>
                <input
                  type="text"
                  value={destAccountId}
                  onChange={(e) => setDestAccountId(e.target.value)}
                  className="w-full px-3 py-2 mt-1 border rounded-md focus:outline-none focus:ring focus:border-blue-300"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  AWS Access Key ID
                </label>
                <input
                  type="text"
                  value={awsDestAccessKeyId}
                  onChange={(e) => setAwsDestAccessKeyId(e.target.value)}
                  className="w-full px-3 py-2 mt-1 border rounded-md focus:outline-none focus:ring focus:border-blue-300"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  AWS Secret Access Key
                </label>
                <input
                  type="password"
                  value={awsDestSecretAccessKey}
                  onChange={(e) => setAwsDestSecretAccessKey(e.target.value)}
                  className="w-full px-3 py-2 mt-1 border rounded-md focus:outline-none focus:ring focus:border-blue-300"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Region Name
                </label>
                <input
                  type="text"
                  value={destRegionName}
                  onChange={(e) => setDestRegionName(e.target.value)}
                  className="w-full px-3 py-2 mt-1 border rounded-md focus:outline-none focus:ring focus:border-blue-300"
                />
              </div>

              <button
                className="w-full px-4 py-2 mt-4 font-bold text-black bg-awsOrange rounded-md hover:bg-awsOrangeDark focus:outline-none "
                onClick={handleMigration}
              >
                Migrate Resources
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* A Modal that pops up when user clicks on Migrate resources: the modal is meant for listing existing VPC's and it prompts the user to select a VPC or click on create a new one button */}
      {selectedInstances.length > 0 && (
        <Modal
          modalInfo={modals}
          handleDone={handleDone}
          isDone={isDone}
          setIsDone={setIsDone}
          handleCancel={handleCancel}
          currentIdx={currentIdx}
          setCurrentIdx={setCurrentIdx}
        />
      )}

      {/* Loading animation used to visualize the satatus of the migration*/}
      {/* Loading animation */}
      {isLoading && (
        <div className="fixed m-0 inset-0 z-50 flex items-center justify-center bg-gray-900 bg-opacity-50 ">
          <div className="w-1/2 p-8 bg-white rounded-lg shadow-md">
            <h1 className="text-2xl py-2 font-bold text-center">
              Migrating Resources
            </h1>
            {/* Icon */}
            <div className="flex justify-center items-center text-blue-500 text-6xl">
              <FaSpinner className="animate-spin" />
            </div>
          </div>
        </div>
      )}

      {/* Done message */}
      {isMigrationDone && (
        <div className="fixed m-0 inset-0 z-50 flex items-center justify-center bg-gray-900 bg-opacity-50 ">
          <div className="w-1/2 p-8 bg-white rounded-lg shadow-md">
            <h1 className="text-2xl py-2 font-bold text-center">
              Migration Done
            </h1>
            {/* Icon */}
            <div className="flex justify-center items-center text-green-500 text-6xl">
              <FaCheckCircle />
            </div>
            <div className="flex justify-end space-x-4">
              <button
                className="px-4 py-2 font-bold text-white bg-awsOrange rounded-md hover:bg-awsOrangeDark focus:outline-none focus:ring focus:border-awsOrangeDark"
                onClick={() => setISMigrationDone(false)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
